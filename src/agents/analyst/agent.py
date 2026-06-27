"""Implements the Analyst Agent responsible for quantitative investment analysis."""

from __future__ import annotations

import json
from typing import Any

import litellm
from litellm.exceptions import RateLimitError

from src.agents.analyst.prompts import ANALYST_TOOLS, build_analyst_prompt
from src.core.config import get_settings
from src.core.exceptions import DataLayerError
from src.core.logging_setup import get_logger
from src.core.state import AgentState, CleanedListing
from src.mcp_servers.postgres_server.repository import ListingRepository
from src.tools.quant_tools import compute_district_statistics

logger = get_logger(__name__)


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


def _fallback_benchmarks(
    cleaned_listings: list[CleanedListing], districts: list[str]
) -> dict[str, float]:
    """Compute price/sqm benchmarks directly from in-memory listings.

    Used when the database has no persisted data yet for the requested
    districts. All math is deterministic, via quant_tools.

    Args:
        cleaned_listings: Cleaned listings currently in pipeline state.
        districts: District names to compute benchmarks for.

    Returns:
        A dict mapping district name to average price_per_sqm.
    """
    benchmarks: dict[str, float] = {}
    for district in districts:
        values = [
            listing.price_per_sqm
            for listing in cleaned_listings
            if listing.district == district
        ]
        if not values:
            continue
        stats = compute_district_statistics(values)
        benchmarks[district] = stats["mean"] if stats else values[0]
    return benchmarks


def _fallback_listings_by_district(
    cleaned_listings: list[CleanedListing], district: str, limit: int
) -> list[dict[str, Any]]:
    """Filter and sort in-memory listings for a district, cheapest first.

    Args:
        cleaned_listings: Cleaned listings currently in pipeline state.
        district: District name to filter by.
        limit: Maximum number of listings to return.

    Returns:
        A list of listing dicts ordered by price_per_sqm ascending.
    """
    matched = [
        listing.model_dump()
        for listing in cleaned_listings
        if listing.district == district
    ]
    matched.sort(key=lambda item: item["price_per_sqm"] or float("inf"))
    return matched[:limit]


async def _execute_db_tool(
    name: str,
    args: dict[str, Any],
    state: AgentState,
    repository: ListingRepository,
) -> str:
    """Execute a database tool, falling back to in-memory computation.

    Args:
        name: The tool name being invoked.
        args: The tool's input arguments.
        state: Current pipeline state, used for the in-memory fallback.
        repository: Repository instance for live database access.

    Returns:
        A JSON string result, mirroring what the live MCP tool would return.
    """
    try:
        if name == "get_price_benchmarks":
            districts = args.get("districts", [])
            result: Any = await repository.get_price_benchmarks(districts)
            if not result:
                result = _fallback_benchmarks(state.cleaned_listings, districts)
        elif name == "get_listings_by_district":
            district = args["district"]
            limit = args.get("limit", 50)
            result = await repository.get_listings_by_district(district, limit)
            if not result:
                result = _fallback_listings_by_district(
                    state.cleaned_listings, district, limit
                )
        else:
            result = {"error": f"Unknown tool: {name}"}
    except DataLayerError:
        logger.debug("DB unavailable, using in-memory fallback", extra={"tool": name})
        if name == "get_price_benchmarks":
            result = _fallback_benchmarks(
                state.cleaned_listings, args.get("districts", [])
            )
        elif name == "get_listings_by_district":
            result = _fallback_listings_by_district(
                state.cleaned_listings, args["district"], args.get("limit", 50)
            )
        else:
            result = {"error": f"Unknown tool: {name}"}
    return json.dumps(result, default=str)


async def _run_analyst_tool_loop(
    messages: list[dict[str, Any]],
    model: str,
    state: AgentState,
    repository: ListingRepository,
) -> str:
    """Call LiteLLM, execute any requested DB tool calls, return final content.

    Args:
        messages: The initial messages array for the LLM call.
        model: The LiteLLM model identifier to use.
        state: Current pipeline state, passed through to the tool executor.
        repository: Repository instance for live database access.

    Returns:
        The final response content string after any tool-call round trip.
    """
    import asyncio as _asyncio

    MAX_RETRIES = 3  # noqa: N806
    for attempt in range(MAX_RETRIES):
        try:
            response = await litellm.acompletion(
                model=model, messages=messages, tools=ANALYST_TOOLS,
                tool_choice="auto", temperature=0.0,
            )
            break  # success — exit retry loop
        except RateLimitError:
            if attempt < MAX_RETRIES - 1:
                wait = 15 * (attempt + 1)  # 15s, 30s, 45s
                logger.warning(
                    "Analyst rate limited — retrying",
                    extra={"attempt": attempt + 1, "wait_seconds": wait},
                )
                await _asyncio.sleep(wait)
            else:
                raise  # exhausted retries — let error handler catch it

    message = response.choices[0].message
    if not getattr(message, "tool_calls", None):
        return message.content or ""

    messages.append(message.model_dump())
    for tool_call in message.tool_calls:
        tool_args = json.loads(tool_call.function.arguments)
        tool_result = await _execute_db_tool(
            tool_call.function.name, tool_args, state, repository
        )
        messages.append(
            {"role": "tool", "tool_call_id": tool_call.id, "content": tool_result}
        )

    final_response = await litellm.acompletion(
        model=model, messages=messages, temperature=0.0
    )
    return final_response.choices[0].message.content or ""


def _compute_benchmarks_from_state(
    cleaned_listings: list[CleanedListing],
) -> dict[str, Any]:
    """Deterministically compute district benchmarks without the LLM.

    Used as a fallback when the analyst LLM's tool-call round trip ends
    with no usable final content (empty string or unparseable JSON).

    Args:
        cleaned_listings: Cleaned listings currently in pipeline state.

    Returns:
        A dict matching the analyst's expected output schema:
        district_analysis, undervalued_listing_ids, overvalued_listing_ids,
        analysis_summary, and top_opportunity.
    """
    from collections import defaultdict
    import statistics

    by_district: dict[str, list[CleanedListing]] = defaultdict(list)
    for listing in cleaned_listings:
        if listing.district and listing.price_per_sqm:
            by_district[listing.district].append(listing)

    district_analysis: dict[str, Any] = {}
    undervalued_ids: list[str] = []
    overvalued_ids: list[str] = []

    for district, listings in by_district.items():
        prices = [listing.price_per_sqm for listing in listings]
        avg_price = statistics.mean(prices)
        district_analysis[district] = {
            "avg_price_per_sqm": avg_price,
            "listing_count": len(listings),
        }
        for listing in listings:
            deviation = (listing.price_per_sqm - avg_price) / avg_price
            if deviation <= -0.20:
                undervalued_ids.append(listing.listing_id)
            elif deviation >= 0.40:
                overvalued_ids.append(listing.listing_id)

    top_opportunity = undervalued_ids[0] if undervalued_ids else None
    analysis_summary = (
        f"Deterministic fallback analysis: {len(district_analysis)} districts, "
        f"{len(undervalued_ids)} undervalued, {len(overvalued_ids)} overvalued listings."
    )

    return {
        "district_analysis": district_analysis,
        "undervalued_listing_ids": undervalued_ids,
        "overvalued_listing_ids": overvalued_ids,
        "analysis_summary": analysis_summary,
        "top_opportunity": top_opportunity,
    }


def _validate_listing_ids(
    candidate_ids: list[str], cleaned_listings: list[CleanedListing]
) -> list[str]:
    """Filter candidate listing IDs to those that actually exist.

    Defends against LLM hallucination of listing IDs.

    Args:
        candidate_ids: Listing IDs returned by the LLM.
        cleaned_listings: Actual cleaned listings in pipeline state.

    Returns:
        The subset of candidate_ids that match a real listing_id.
    """
    actual_ids = {listing.listing_id for listing in cleaned_listings}
    return [listing_id for listing_id in candidate_ids if listing_id in actual_ids]


async def analyst_node(state: AgentState) -> dict[str, Any]:
    """Execute the Analyst Agent node.

    Calls get_price_benchmarks via tool use, then identifies
    undervalued and overvalued listings against district benchmarks.

    Args:
        state: AgentState with cleaned_listings populated.

    Returns:
        Partial state update with benchmarks, undervalued IDs, summary.
    """
    if not state.cleaned_listings:
        return {
            "current_phase": "analysis_skipped",
            "analysis_summary": "No cleaned listings available.",
        }

    settings = get_settings()
    repository = ListingRepository()
    # Send only essential fields to reduce token usage
    listings_dicts = [
        {
            "listing_id": listing.listing_id,
            "district": listing.district,
            "price_per_sqm": listing.price_per_sqm,
            "area_sqm": listing.area_sqm,
            "property_type": listing.property_type,
            "price_sar": listing.price_sar,
        }
        for listing in state.cleaned_listings
        if listing.district and listing.price_per_sqm
    ]
    districts = list({listing.district for listing in state.cleaned_listings})

    try:
        messages = build_analyst_prompt(listings_dicts, districts)
        content = await _run_analyst_tool_loop(
            messages, settings.litellm_model, state, repository
        )
        if not content or not content.strip():
            logger.warning(
                "Analyst LLM returned empty content — using deterministic fallback",
                extra={"run_id": state.run_id},
            )
            analysis_result = _compute_benchmarks_from_state(state.cleaned_listings)
        else:
            try:
                analysis_result = json.loads(_strip_code_fences(content))
            except json.JSONDecodeError as exc:
                logger.warning(
                    "Analyst LLM returned unparseable JSON — using deterministic fallback",
                    extra={"run_id": state.run_id, "error": str(exc)},
                )
                analysis_result = _compute_benchmarks_from_state(state.cleaned_listings)
    except Exception as exc:
        logger.error("Analyst agent failed", exc_info=True, extra={"run_id": state.run_id})
        return {
            "current_phase": "analysis_failed",
            "errors": [{"phase": "analysis", "error": str(exc), "run_id": state.run_id}],
        }

    district_analysis = analysis_result.get("district_analysis", {})
    district_benchmarks = {
        district: values["avg_price_per_sqm"]
        for district, values in district_analysis.items()
        if "avg_price_per_sqm" in values
    }
    candidate_undervalued_ids = analysis_result.get("undervalued_listing_ids", [])
    validated_undervalued_ids = _validate_listing_ids(
        candidate_undervalued_ids, state.cleaned_listings
    )
    if len(validated_undervalued_ids) != len(candidate_undervalued_ids):
        logger.warning(
            "Some undervalued listing IDs failed validation",
            extra={
                "run_id": state.run_id,
                "candidate_count": len(candidate_undervalued_ids),
                "validated_count": len(validated_undervalued_ids),
            },
        )
    analysis_summary = analysis_result.get("analysis_summary", "")

    logger.info(
        "Analyst agent completed",
        extra={
            "run_id": state.run_id,
            "undervalued_count": len(validated_undervalued_ids),
        },
    )
    return {
        "district_benchmarks": district_benchmarks,
        "undervalued_listing_ids": validated_undervalued_ids,
        "analysis_summary": analysis_summary,
        "current_phase": "analysis_complete",
    }
