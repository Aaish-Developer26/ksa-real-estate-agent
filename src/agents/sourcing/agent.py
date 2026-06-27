"""Implements the Sourcing Agent responsible for raw listing extraction."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import litellm
from pydantic import ValidationError

from src.agents.sourcing.prompts import SOURCING_TOOLS, build_sourcing_prompt
from src.core.config import get_settings
from src.core.exceptions import IngestionError
from src.core.logging_setup import get_logger
from src.core.state import AgentState, RawListing
from src.mcp_servers.search_server.server import app as search_app

logger = get_logger(__name__)

DEFAULT_DISTRICTS: list[str] = [
    "Olaya",
    "Al_Malqa",
    "Al_Nakheel",
    "Al_Rawdah",
    "KAFD",
    "Al_Naseem",
]

_MOCK_DATA_PATH = Path("data/mock/riyadh_listings.json")


async def _execute_search_tool(tool_name: str, tool_args: dict[str, Any]) -> str:
    """Simulate a search MCP tool call using the local mock dataset.

    Stands in for a live ``search_app`` (registered as ``%s``) stdio
    connection during development, since the graph does not yet spawn a
    live MCP subprocess.

    Args:
        tool_name: The name of the tool being invoked.
        tool_args: The tool's input arguments.

    Returns:
        A JSON string result, mirroring what the live MCP tool would return.
    """
    logger.debug(
        "Executing search tool", extra={"tool": tool_name, "tool_args": tool_args}
    )
    if tool_name == "search_real_estate":
        return await _mock_search_real_estate(tool_args.get("query", ""))
    if tool_name == "search_market_news":
        return json.dumps(
            [{"title": "Riyadh real estate market update", "url": "", "snippet": ""}]
        )
    return json.dumps({"error": f"Unknown tool: {tool_name}"})


_execute_search_tool.__doc__ = (_execute_search_tool.__doc__ or "") % search_app.name


async def _mock_search_real_estate(query: str) -> str:
    """Return mock listings whose district appears in the query string.

    Args:
        query: The search query, expected to mention a district name.

    Returns:
        A JSON string list of raw listing dicts.
    """

    def _read_mock_listings() -> list[dict[str, Any]]:
        with _MOCK_DATA_PATH.open(encoding="utf-8") as handle:
            data: dict[str, Any] = json.load(handle)
        return list(data["listings"])

    listings = await asyncio.to_thread(_read_mock_listings)
    matched = [
        listing
        for listing in listings
        if listing.get("raw_location", "").replace(" ", "_").lower()
        in query.replace(" ", "_").lower()
        or query.replace(" ", "_").lower() in listing.get("raw_location", "").replace(" ", "_").lower()
    ]
    return json.dumps(matched)


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


def _parse_raw_listings(content: str) -> list[RawListing]:
    """Parse LLM response content into validated RawListing objects.

    Args:
        content: Final LLM response content, expected to be a JSON list.

    Returns:
        List of successfully validated RawListing instances. Items that
        fail validation are logged and skipped — partial results are
        acceptable for sourcing.
    """
    raw_listings: list[RawListing] = []
    try:
        items = json.loads(_strip_code_fences(content))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse sourcing response as JSON", extra={"error": str(exc)})
        return raw_listings

    if not isinstance(items, list):
        logger.warning("Sourcing response JSON was not a list")
        return raw_listings

    for item in items:
        try:
            item.setdefault("scraped_at", datetime.now(timezone.utc).isoformat())
            raw_listings.append(RawListing(**item))
        except (ValidationError, TypeError, AttributeError) as exc:
            logger.warning("Skipping invalid raw listing", extra={"error": str(exc)})
    return raw_listings


def _load_mock_raw_listings() -> list[RawListing]:
    """Load raw listings directly from the local mock dataset, bypassing the LLM.

    Used as a fast-path in development so the pipeline doesn't depend
    on the LLM reliably echoing back structured JSON for data that is
    already structured.

    Returns:
        List of successfully validated RawListing instances. Invalid
        records are logged and skipped.
    """
    mock_path = (
        Path(__file__).parent.parent.parent.parent
        / "data"
        / "mock"
        / "riyadh_listings.json"
    )
    with mock_path.open(encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)

    raw_listings: list[RawListing] = []
    for listing_dict in data["listings"]:
        try:
            raw_listings.append(RawListing(**listing_dict))
        except (ValidationError, TypeError) as exc:
            logger.warning("Skipping invalid mock listing", extra={"error": str(exc)})
    return raw_listings


async def _run_tool_call_loop(
    messages: list[dict[str, Any]], settings_model: str
) -> str:
    """Call LiteLLM, execute any requested tool calls, and return final content.

    Args:
        messages: The initial messages array for the LLM call.
        settings_model: The LiteLLM model identifier to use.

    Returns:
        The final response content string after any tool-call round trip.
    """
    response = await litellm.acompletion(
        model=settings_model,
        messages=messages,
        tools=SOURCING_TOOLS,
        tool_choice="auto",
        temperature=0.1,
    )
    message = response.choices[0].message
    if not getattr(message, "tool_calls", None):
        return message.content or ""

    messages.append(message.model_dump())
    for tool_call in message.tool_calls:
        tool_args = json.loads(tool_call.function.arguments)
        tool_result = await _execute_search_tool(tool_call.function.name, tool_args)
        messages.append(
            {"role": "tool", "tool_call_id": tool_call.id, "content": tool_result}
        )

    final_response = await litellm.acompletion(
        model=settings_model, messages=messages, temperature=0.1
    )
    return final_response.choices[0].message.content or ""


async def sourcing_node(state: AgentState) -> dict[str, Any]:
    """Execute the Sourcing Agent node in the LangGraph graph.

    Searches for real estate listings across specified Riyadh districts
    using the Brave Search MCP tools. Updates AgentState with raw
    listings and advances the pipeline phase.

    Args:
        state: Current AgentState containing pipeline metadata.

    Returns:
        Partial state update dict with raw_listings and current_phase.
    """
    logger.info(
        "Sourcing agent started",
        extra={"run_id": state.run_id, "current_phase": state.current_phase},
    )

    use_mock = os.getenv("APP_ENV", "development") == "development"
    if use_mock:
        raw_listings = _load_mock_raw_listings()
        logger.info(f"Mock data fast-path: loaded {len(raw_listings)} listings")
        return {
            "raw_listings": raw_listings,
            "current_phase": "sourcing_complete",
            "errors": [],
        }

    settings = get_settings()
    try:
        messages = build_sourcing_prompt(DEFAULT_DISTRICTS)
        content = await _run_tool_call_loop(messages, settings.litellm_model)
        raw_listings = _parse_raw_listings(content)
        logger.info(
            "Sourcing agent completed",
            extra={"run_id": state.run_id, "listing_count": len(raw_listings)},
        )
        return {"raw_listings": raw_listings, "current_phase": "sourcing_complete"}
    except IngestionError as exc:
        logger.error(
            "Sourcing agent failed with ingestion error",
            exc_info=True,
            extra={"run_id": state.run_id},
        )
        return {
            "current_phase": "sourcing_failed",
            "errors": [{"phase": "sourcing", "error": str(exc), "run_id": state.run_id}],
        }
    except Exception as exc:
        logger.error(
            "Sourcing agent failed unexpectedly",
            exc_info=True,
            extra={"run_id": state.run_id},
        )
        return {
            "current_phase": "sourcing_failed",
            "errors": [{"phase": "sourcing", "error": str(exc), "run_id": state.run_id}],
        }
