"""Prompt templates and tool schemas for the Analyst Agent."""

from __future__ import annotations

import json
from typing import Any

ANALYST_SYSTEM_PROMPT: str = """You are a quantitative real estate investment analyst
specializing in the Riyadh market. You are rigorous,
data-driven, and conservative in your assessments.

Critical rules:
- ALWAYS call get_price_benchmarks before any price assessment
- Never estimate or guess price benchmarks from memory
- A listing is undervalued if price_per_sqm < (district_avg × 0.80)
- Flag listings as overvalued if price_per_sqm > (district_avg × 1.40)
- Minimum 5 listings per district for a valid benchmark
- If fewer than 5 listings exist for a district, mark benchmark
  as 'insufficient_data' and skip undervalued detection for that district"""

ANALYST_OUTPUT_SCHEMA: dict[str, Any] = {
    "district_analysis": {
        "<district_name>": {
            "avg_price_per_sqm": 0.0,
            "listing_count": 0,
            "min_price_per_sqm": 0.0,
            "max_price_per_sqm": 0.0,
            "data_quality": "sufficient|insufficient_data",
        }
    },
    "undervalued_listing_ids": ["string"],
    "overvalued_listing_ids": ["string"],
    "analysis_summary": "string — 3-5 sentence investment narrative",
    "top_opportunity": {
        "listing_id": "string",
        "district": "string",
        "discount_pct": 0.0,
        "reason": "string",
    },
}

ANALYST_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_price_benchmarks",
            "description": "Get average price per sqm benchmarks by district",
            "parameters": {
                "type": "object",
                "properties": {
                    "districts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["districts"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_listings_by_district",
            "description": "Retrieve cleaned listings filtered by Riyadh district",
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["district"],
            },
        },
    },
]


def build_analyst_prompt(
    cleaned_listings: list[dict[str, Any]],
    districts: list[str],
) -> list[dict[str, str]]:
    """Build the messages array for the analyst agent LLM call.

    Args:
        cleaned_listings: Normalized listing dicts for analysis.
        districts: Unique district names present in listings.

    Returns:
        Messages array for the LiteLLM call.
    """
    user_content = f"""Analyze these {len(cleaned_listings)} cleaned Riyadh
real estate listings across districts: {', '.join(districts)}

Steps:
1. Call get_price_benchmarks with these districts to obtain ground-truth
   average price_per_sqm per district. Never estimate this yourself.
2. Classify each listing as undervalued, overvalued, or neither based
   on the rules in your system prompt.
3. Identify the single best investment opportunity.

Listings:
{json.dumps(cleaned_listings, ensure_ascii=False, indent=2, default=str)}

Return ONLY this JSON schema, no other text:
{json.dumps(ANALYST_OUTPUT_SCHEMA, indent=2)}"""

    return [
        {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
