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


async def _execute_search_tool(
    tool_name: str,
    tool_args: dict[str, Any],
) -> str:
    """Execute a search tool call.

    In development mode: returns filtered mock data.
    In production mode: calls real Brave Search API.

    Args:
        tool_name: Name of the tool to execute.
        tool_args: Tool arguments from LLM tool call.

    Returns:
        JSON string of search results.
    """
    import os
    import json as _json

    app_env = os.getenv("APP_ENV", "development")

    if app_env != "development":
        # PRODUCTION: Call real Brave Search API
        try:
            from src.mcp_servers.search_server.server import (
                _brave_search,
            )
            if tool_name == "search_real_estate":
                query = tool_args.get("query", "")
                count = tool_args.get("count", 10)
                logger.debug(
                    "Production search tool call",
                    extra={
                        "tool": tool_name,
                        "query": query,
                        "count": count,
                    },
                )
                results = await _brave_search(query, count)
                return _json.dumps(results)

            elif tool_name == "search_market_news":
                query = tool_args.get("query", "")
                count = tool_args.get("count", 5)
                results = await _brave_search(query, count)
                return _json.dumps(results)

            else:
                logger.warning(
                    "Unknown tool in production mode",
                    extra={"tool_name": tool_name},
                )
                return _json.dumps([])

        except Exception as e:
            logger.error(
                "Production search tool failed",
                extra={
                    "tool": tool_name,
                    "error": str(e),
                },
            )
            return _json.dumps([])

    else:
        # DEVELOPMENT: Use mock data fast-path
        try:
            from pathlib import Path
            mock_path = (
                Path(__file__).parent.parent.parent.parent
                / "data"
                / "mock"
                / "riyadh_listings.json"
            )
            with open(mock_path, encoding="utf-8") as f:
                import json as _json2
                mock_data = _json2.load(f)

            all_listings = mock_data.get("listings", [])
            query = tool_args.get("query", "").lower()

            # Filter by district if query contains district name
            filtered = [
                lst for lst in all_listings
                if any(
                    term in query
                    for term in [
                        lst.get("raw_location", "").lower(),
                        lst.get("listing_id", "").lower(),
                    ]
                )
            ] or all_listings[:10]

            logger.debug(
                "Mock search tool call",
                extra={
                    "tool": tool_name,
                    "results": len(filtered),
                },
            )
            return _json.dumps(filtered[:10])

        except Exception as e:
            logger.error(
                "Mock search tool failed",
                extra={"error": str(e)},
            )
            return _json.dumps([])


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
    items = _extract_json_from_response(content)

    if not items:
        logger.warning(
            "Sourcing: no listings extracted from LLM response",
            extra={"content_preview": content[:300]},
        )
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
    from litellm.exceptions import (
        RateLimitError,
        ServiceUnavailableError,
    )

    MAX_RETRIES = 4
    try:
        response = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await litellm.acompletion(
                    model=settings_model,
                    messages=messages,
                    tools=SOURCING_TOOLS,
                    tool_choice="auto",
                    temperature=0.1,
                )
                break  # success — exit retry loop
            except (RateLimitError, ServiceUnavailableError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 20 * (attempt + 1)  # 20s, 40s, 60s
                    logger.warning(
                        "Sourcing LLM unavailable — retrying",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": MAX_RETRIES,
                            "wait_seconds": wait,
                            "error": str(e)[:100],
                        }
                    )
                    import asyncio as _asyncio
                    await _asyncio.sleep(wait)
                else:
                    logger.error(
                        "Sourcing LLM failed after all retries",
                        extra={"attempts": MAX_RETRIES, "error": str(e)[:200]}
                    )
                    raise

        if response is None:
            logger.error("Sourcing: no response after retries")
            return ""

        if not response.choices:
            logger.warning(
                "LLM returned empty choices list",
                extra={"model": settings_model},
            )
            return ""

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        content = getattr(message, "content", None) or ""

        finish_reason = getattr(response.choices[0], "finish_reason", "") or ""
        # Gemini uses 'STOP', Groq uses 'stop'
        is_done = finish_reason.upper() in ("STOP", "END", "LENGTH")
        has_tool_calls = bool(tool_calls)

        if not has_tool_calls and not content:
            logger.warning(
                "LLM returned no tool calls and no content",
                extra={
                    "finish_reason": finish_reason,
                    "model": settings_model,
                },
            )
            return ""

        if not has_tool_calls:
            return content

        messages.append(message.model_dump())
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, ValueError):
                tool_args = {}

            tool_result = await _execute_search_tool(tool_name, tool_args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

        final_response = None
        for attempt in range(MAX_RETRIES):
            try:
                final_response = await litellm.acompletion(
                    model=settings_model, messages=messages, temperature=0.1
                )
                break
            except (RateLimitError, ServiceUnavailableError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 20 * (attempt + 1)
                    logger.warning(
                        "Sourcing final LLM call retrying",
                        extra={"attempt": attempt + 1, "wait": wait}
                    )
                    import asyncio as _asyncio
                    await _asyncio.sleep(wait)
                else:
                    raise

        if not final_response.choices:
            logger.warning(
                "LLM returned empty choices list on final response",
                extra={"model": settings_model},
            )
            return ""

        final_message = final_response.choices[0].message
        return getattr(final_message, "content", None) or ""
    except IndexError as e:
        logger.error(
            "Index error in tool call loop — "
            "likely empty LLM response",
            extra={"error": str(e), "model": settings_model},
        )
        return ""


def _extract_json_from_response(text: str) -> list:
    """Extract JSON array from LLM response text.

    Handles three cases:
    1. Pure JSON array: [...]
    2. JSON embedded in markdown: ```json\n[...]\n```
    3. JSON embedded in prose: "Here are the listings: [...]"

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed list or empty list if extraction fails.
    """
    if not text or not text.strip():
        return []

    # Case 1: Try direct JSON parse first
    try:
        result = json.loads(text.strip())
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and 'listings' in result:
            return result['listings']
    except (json.JSONDecodeError, ValueError):
        pass

    # Case 2: Extract from markdown code blocks
    import re
    code_block = re.search(
        r'```(?:json)?\s*(\[.*?\])\s*```',
        text,
        re.DOTALL
    )
    if code_block:
        try:
            result = json.loads(code_block.group(1))
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Case 3: Find first [ to last ] in the text
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1 and end > start:
        try:
            result = json.loads(text[start:end + 1])
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning(
        "Could not extract JSON from sourcing response",
        extra={"content_preview": text[:200]}
    )
    return []


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
