"""Prompt templates and tool schemas for the Sourcing Agent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SOURCING_SYSTEM_PROMPT: str = """You are a specialized real estate data sourcing agent for the
Riyadh, Saudi Arabia market. Your sole responsibility is to search
for property listings using the available search tools and return
raw, unmodified data.

Rules you must follow:
- Always call search_real_estate at least once per district requested
- Never modify, clean, or interpret listing data — return it raw
- Always include the source URL for every listing found
- If search returns no results for a district, log it and continue
- Extract listing_id from URL patterns when possible
- Always record scraped_at as current UTC ISO timestamp
- Target these districts unless instructed otherwise:
  Olaya, Al_Malqa, Al_Nakheel, Al_Rawdah, KAFD, Al_Naseem"""


def build_sourcing_prompt(
    districts: list[str],
    max_listings_per_district: int = 10,
) -> list[dict[str, str]]:
    """Build the messages array for the sourcing agent LLM call.

    Args:
        districts: List of Riyadh district names to search.
        max_listings_per_district: Max listings to retrieve per district.

    Returns:
        List of message dicts with role and content keys.
    """
    user_content = f"""Search for real estate listings in these
Riyadh districts: {', '.join(districts)}

For each district:
1. Call search_real_estate with query:
   "<district> real estate listings for sale Riyadh"
2. Extract up to {max_listings_per_district} listings
3. For each listing extract all available fields

CRITICAL: Your FINAL response after all tool calls must be
ONLY a valid JSON array. No prose. No explanation.
No markdown. Just the raw JSON array starting with [

Required JSON format:
[
  {{
    "listing_id": "unique-id-from-url-or-generate",
    "source_url": "full URL from search result",
    "raw_title": "listing title as found",
    "raw_price": "price as found in text",
    "raw_area": "area as found in text",
    "raw_location": "location/district as found",
    "raw_property_type": "villa/apartment/land/etc",
    "raw_description": "description snippet",
    "rera_number": "10-digit number if found else null",
    "is_waqf": false,
    "scraped_at": "{datetime.now(timezone.utc).isoformat()}"
  }}
]

If no listings found for a district, skip it.
Return [] if absolutely no listings found anywhere.
REMEMBER: Return ONLY the JSON array, nothing else."""

    return [
        {"role": "system", "content": SOURCING_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


SOURCING_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_real_estate",
            "description": "Search for real estate listings in Riyadh",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_market_news",
            "description": "Search for Riyadh real estate market news",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "count": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
]
