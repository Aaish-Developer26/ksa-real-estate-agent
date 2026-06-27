"""Implements the Brave Search MCP server for Riyadh real estate research."""

from __future__ import annotations

import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.core.config import get_settings
from src.core.exceptions import MCPServerError, ScrapingRateLimitError
from src.core.logging_setup import get_logger, setup_logging

logger = get_logger(__name__)

app: Server = Server("brave-search-server")

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


@app.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_tools() -> list[Tool]:
    """List the search tools exposed by this MCP server.

    Returns:
        The 2 tools available for real estate listing and market news search.
    """
    return [
        Tool(
            name="search_real_estate",
            description="Search for real estate listings in Riyadh",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="search_market_news",
            description="Search for Riyadh real estate market news and trends",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


async def _brave_search(query: str, count: int) -> list[dict[str, str]]:
    """Call the Brave Search API and extract title/url/snippet results.

    Args:
        query: The fully enhanced search query string.
        count: Number of results to request.

    Returns:
        A list of dicts with "title", "url", and "snippet" keys.

    Raises:
        ScrapingRateLimitError: If Brave Search returns HTTP 429.
        MCPServerError: On timeout or any other non-2xx HTTP response.
    """
    settings = get_settings()
    headers = {"X-Subscription-Token": settings.brave_search_api_key.get_secret_value()}
    params: dict[str, str | int] = {
        "q": query,
        "count": count,
        "country": "SA",
        "search_lang": "ar",
        "ui_lang": "en-US",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                _BRAVE_SEARCH_URL, headers=headers, params=params, timeout=10.0
            )
    except httpx.TimeoutException as exc:
        logger.error("Brave Search request timed out", exc_info=True)
        raise MCPServerError(
            "Brave Search request timed out", context={"query": query}
        ) from exc

    if response.status_code == 429:
        logger.error("Brave Search rate limit exceeded", extra={"query": query})
        raise ScrapingRateLimitError(
            "Brave Search rate limit exceeded", context={"query": query}
        )
    if response.status_code >= 400:
        logger.error(
            "Brave Search request failed",
            extra={"query": query, "status_code": response.status_code},
        )
        raise MCPServerError(
            "Brave Search request failed",
            context={"query": query, "status_code": str(response.status_code)},
        )

    payload = response.json()
    results = payload.get("web", {}).get("results", [])
    return [
        {
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "snippet": result.get("description", ""),
        }
        for result in results
    ]


@app.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch a search tool call to the Brave Search API.

    Args:
        name: The tool name being invoked.
        arguments: The tool's input arguments, matching its inputSchema.

    Returns:
        A single ``TextContent`` item containing the JSON-serialized
        search results, or a JSON-serialized ``{"error": ...}`` payload
        on failure.
    """
    try:
        if name == "search_real_estate":
            query = (
                f"{arguments['query']} Riyadh real estate site:aqar.sa "
                "OR site:bayut.sa OR site:propertyfinder.ae"
            )
            count = arguments.get("count", 10)
            result = await _brave_search(query, count)
        elif name == "search_market_news":
            query = f"{arguments['query']} Riyadh real estate market 2024 Saudi Arabia"
            count = arguments.get("count", 5)
            result = await _brave_search(query, count)
        else:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": f"Unknown tool: {name}"})
                )
            ]
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as exc:
        logger.error("Search tool call failed", exc_info=True, extra={"tool": name})
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def main() -> None:
    """Run the Brave Search MCP server over stdio."""
    setup_logging()
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
