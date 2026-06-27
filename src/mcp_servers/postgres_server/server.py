"""Implements the custom Postgres MCP server exposing listing repository tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.core.database import close_pool, initialize_pool
from src.core.logging_setup import get_logger, setup_logging
from src.mcp_servers.postgres_server.repository import ListingRepository

logger = get_logger(__name__)

app: Server = Server("postgres-listing-server")
repository = ListingRepository()


@app.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
async def list_tools() -> list[Tool]:
    """List the database tools exposed by this MCP server.

    Returns:
        The 8 tools available for listing ingestion, persistence, and
        analytics queries.
    """
    return [
        Tool(
            name="load_mock_data",
            description="Load Riyadh mock listings from JSON file into database",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {"type": "string"},
                    "run_id": {"type": "string"},
                },
                "required": ["filepath", "run_id"],
            },
        ),
        Tool(
            name="create_analysis_run",
            description="Create a new pipeline analysis run record",
            inputSchema={
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
            },
        ),
        Tool(
            name="update_analysis_run",
            description="Update analysis run status and completion summary",
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "status": {"type": "string"},
                    "summary": {"type": "string"},
                    "total_listings": {"type": "integer"},
                },
                "required": ["run_id", "status"],
            },
        ),
        Tool(
            name="insert_raw_listings",
            description="Bulk insert raw scraped listings into database",
            inputSchema={
                "type": "object",
                "properties": {
                    "listings": {"type": "array", "items": {"type": "object"}},
                    "run_id": {"type": "string"},
                },
                "required": ["listings", "run_id"],
            },
        ),
        Tool(
            name="insert_cleaned_listings",
            description="Bulk insert normalized listings into database",
            inputSchema={
                "type": "object",
                "properties": {
                    "listings": {"type": "array", "items": {"type": "object"}},
                    "run_id": {"type": "string"},
                },
                "required": ["listings", "run_id"],
            },
        ),
        Tool(
            name="insert_compliance_flags",
            description="Insert compliance flags for listings",
            inputSchema={
                "type": "object",
                "properties": {
                    "flags": {"type": "array", "items": {"type": "object"}},
                    "run_id": {"type": "string"},
                },
                "required": ["flags", "run_id"],
            },
        ),
        Tool(
            name="get_listings_by_district",
            description="Retrieve cleaned listings filtered by Riyadh district",
            inputSchema={
                "type": "object",
                "properties": {
                    "district": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["district"],
            },
        ),
        Tool(
            name="get_price_benchmarks",
            description="Get average price per sqm benchmarks by district",
            inputSchema={
                "type": "object",
                "properties": {
                    "districts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["districts"],
            },
        ),
    ]


@app.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch a tool call to the corresponding repository method.

    Args:
        name: The tool name being invoked.
        arguments: The tool's input arguments, matching its inputSchema.

    Returns:
        A single ``TextContent`` item containing the JSON-serialized
        result, or a JSON-serialized ``{"error": ...}`` payload on failure.
    """
    try:
        if name == "load_mock_data":
            result: Any = await repository.load_mock_data(
                arguments["filepath"], arguments["run_id"]
            )
        elif name == "create_analysis_run":
            result = await repository.create_analysis_run(arguments["run_id"])
        elif name == "update_analysis_run":
            result = await repository.update_analysis_run(
                arguments["run_id"],
                arguments["status"],
                arguments.get("summary", ""),
                arguments.get("total_listings", 0),
            )
        elif name == "insert_raw_listings":
            result = await repository.insert_raw_listings(
                arguments["listings"], arguments["run_id"]
            )
        elif name == "insert_cleaned_listings":
            result = await repository.insert_cleaned_listings(
                arguments["listings"], arguments["run_id"]
            )
        elif name == "insert_compliance_flags":
            result = await repository.insert_compliance_flags(
                arguments["flags"], arguments["run_id"]
            )
        elif name == "get_listings_by_district":
            result = await repository.get_listings_by_district(
                arguments["district"], arguments.get("limit", 50)
            )
        elif name == "get_price_benchmarks":
            result = await repository.get_price_benchmarks(arguments["districts"])
        else:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": f"Unknown tool: {name}"})
                )
            ]
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as exc:
        logger.error("Tool call failed", exc_info=True, extra={"tool": name})
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]


async def main() -> None:
    """Initialize the database pool and run the MCP server over stdio."""
    setup_logging()
    await initialize_pool()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    finally:
        await close_pool()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
