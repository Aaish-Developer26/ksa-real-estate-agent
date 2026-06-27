"""Implements the Cleaning Agent responsible for listing normalization.

Uses a two-pass approach: deterministic numeric normalization
(normalizer.py) followed by LLM-based semantic enrichment (prompts.py).
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import litellm
from pydantic import ValidationError

from src.agents.cleaning.normalizer import (
    compute_price_per_sqm,
    extract_rera_number,
    normalize_district,
    normalize_property_type,
    parse_area_sqm,
    parse_price_sar,
)
from src.agents.cleaning.prompts import build_cleaning_prompt
from src.core.config import get_settings
from src.core.logging_setup import get_logger
from src.core.state import AgentState, CleanedListing, RawListing

logger = get_logger(__name__)

_FOREIGN_OWNERSHIP_APPROVED_ZONES = {"KAFD", "Diplomatic_Quarter", "DQ"}


def _strip_code_fences(content: str) -> str:
    """Remove surrounding Markdown code fences from an LLM response.

    Args:
        content: Raw LLM response text, possibly fenced with ```json ... ```.

    Returns:
        The content with leading/trailing code fences removed.
    """
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
    return stripped.strip()


def _deterministic_pass(raw_listings: list[RawListing]) -> list[dict[str, Any]]:
    """Apply deterministic numeric/textual normalization to raw listings.

    Args:
        raw_listings: Raw listings sourced by the Sourcing Agent.

    Returns:
        List of partially-cleaned dicts with deterministic fields filled in.
    """
    results: list[dict[str, Any]] = []
    for idx, raw_listing in enumerate(raw_listings):
        listing_dict = raw_listing.model_dump()
        price_sar = parse_price_sar(listing_dict.get("raw_price"))
        area_sqm = parse_area_sqm(listing_dict.get("raw_area"))
        results.append(
            {
                "listing_id": listing_dict.get("listing_id") or f"unknown-{idx}",
                "source_url": listing_dict.get("source_url") or "",
                "raw_title": listing_dict.get("raw_title"),
                "price_sar": price_sar,
                "area_sqm": area_sqm,
                "price_per_sqm": compute_price_per_sqm(price_sar, area_sqm),
                "district": normalize_district(listing_dict.get("raw_location")),
                "property_type": normalize_property_type(
                    listing_dict.get("raw_property_type")
                ),
                "rera_number": extract_rera_number(
                    listing_dict.get("rera_number")
                    or listing_dict.get("raw_description")
                ),
                "is_waqf": listing_dict.get("is_waqf", False),
            }
        )
    return results


async def _semantic_pass(
    raw_listings: list[RawListing], model: str
) -> dict[str, dict[str, Any]]:
    """Run the LLM semantic enrichment pass over raw listings.

    Batched to respect Groq free-tier TPM rate limits: at most
    BATCH_SIZE listings are sent per LLM call, with a pause between
    batches.

    Args:
        raw_listings: Raw listings to translate and semantically enrich.
        model: The LiteLLM model identifier to use.

    Returns:
        A lookup dict mapping listing_id to its semantic enrichment dict.
        Batches that fail are logged and skipped — cleaning proceeds
        with deterministic results only for those listings (graceful
        degradation).
    """
    BATCH_SIZE = 10  # noqa: N806
    BATCH_SLEEP_SECONDS = 10  # noqa: N806
    semantic_lookup: dict[str, dict[str, Any]] = {}

    raw_dicts_for_llm = [rl.model_dump() for rl in raw_listings]

    for batch_start in range(0, len(raw_dicts_for_llm), BATCH_SIZE):
        batch = raw_dicts_for_llm[batch_start : batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(raw_dicts_for_llm) + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(
            "Processing cleaning batch",
            extra={
                "batch": batch_num,
                "total_batches": total_batches,
                "batch_size": len(batch),
            },
        )

        try:
            messages = build_cleaning_prompt(batch)
            response = await litellm.acompletion(
                model=model, messages=messages, temperature=0.1
            )
            content = response.choices[0].message.content or ""
            parsed = json.loads(_strip_code_fences(content))
            items = parsed.get("cleaned_items", [])
            for item in items:
                listing_id = item.get("listing_id")
                if listing_id:
                    semantic_lookup[listing_id] = item
        except Exception as exc:
            logger.error(
                "Cleaning batch LLM failed — using deterministic only",
                exc_info=True,
                extra={"batch": batch_num, "error": str(exc)},
            )

        if batch_start + BATCH_SIZE < len(raw_dicts_for_llm):
            logger.info(
                "Rate limit pause between batches",
                extra={"sleep_seconds": BATCH_SLEEP_SECONDS},
            )
            await asyncio.sleep(BATCH_SLEEP_SECONDS)

    return semantic_lookup


def _merge_entry(
    entry: dict[str, Any], semantic: dict[str, Any], normalized_at: str
) -> dict[str, Any]:
    """Merge a deterministic entry with its semantic enrichment result.

    Args:
        entry: Deterministic fields for one listing.
        semantic: Semantic enrichment dict for the same listing (may be empty).
        normalized_at: ISO timestamp to stamp on the merged listing.

    Returns:
        A dict matching the CleanedListing schema, ready for validation.
    """
    district = entry["district"] or semantic.get("inferred_district")
    property_type = entry["property_type"]
    if property_type == "other":
        property_type = semantic.get("inferred_property_type", "other")
    return {
        "listing_id": entry["listing_id"],
        "source_url": entry["source_url"],
        "title_en": semantic.get("title_en") or entry.get("raw_title") or "",
        "price_sar": entry["price_sar"],
        "area_sqm": entry["area_sqm"],
        "price_per_sqm": entry["price_per_sqm"],
        "district": district,
        "property_type": property_type,
        "rera_number": entry["rera_number"],
        "is_waqf": entry["is_waqf"],
        "is_foreign_ownership_restricted": district is not None
        and district not in _FOREIGN_OWNERSHIP_APPROVED_ZONES,
        "normalized_at": normalized_at,
    }


def _merge_and_validate(
    partial: list[dict[str, Any]], semantic_lookup: dict[str, dict[str, Any]]
) -> list[CleanedListing]:
    """Merge deterministic and semantic results, validating each as CleanedListing.

    Args:
        partial: Deterministic per-listing dicts from _deterministic_pass.
        semantic_lookup: Semantic enrichment dicts keyed by listing_id.

    Returns:
        List of successfully validated CleanedListing instances. Listings
        that fail validation are logged and dropped.
    """
    cleaned: list[CleanedListing] = []
    normalized_at = datetime.now(timezone.utc).isoformat()
    for entry in partial:
        semantic = semantic_lookup.get(entry["listing_id"], {})
        merged = _merge_entry(entry, semantic, normalized_at)
        try:
            cleaned.append(CleanedListing(**merged))
        except ValidationError as exc:
            logger.warning(
                "Dropping listing that failed CleanedListing validation",
                extra={"listing_id": entry["listing_id"], "error": str(exc)},
            )
    return cleaned


async def cleaning_node(state: AgentState) -> dict[str, Any]:
    """Execute the Cleaning Agent node.

    Two-pass cleaning: deterministic normalization first, then
    LLM-based semantic enrichment.

    Args:
        state: Current AgentState with raw_listings populated.

    Returns:
        Partial state update with cleaned_listings and current_phase.
    """
    if not state.raw_listings:
        logger.warning("No raw listings to clean", extra={"run_id": state.run_id})
        return {"current_phase": "cleaning_skipped", "cleaned_listings": []}

    settings = get_settings()
    partial = _deterministic_pass(state.raw_listings)
    semantic_lookup = await _semantic_pass(state.raw_listings, settings.litellm_model)
    cleaned_listings = _merge_and_validate(partial, semantic_lookup)

    logger.info(
        "Cleaning complete",
        extra={
            "run_id": state.run_id,
            "raw_count": len(state.raw_listings),
            "cleaned_count": len(cleaned_listings),
            "dropped_count": len(state.raw_listings) - len(cleaned_listings),
        },
    )
    return {"cleaned_listings": cleaned_listings, "current_phase": "cleaning_complete"}
