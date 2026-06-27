"""Prompt templates for the Cleaning Agent's semantic enrichment pass."""

from __future__ import annotations

import json
from typing import Any

CLEANING_SYSTEM_PROMPT: str = """You are a bilingual (Arabic/English) data normalization agent
specializing in Saudi real estate listings. You handle ONLY the
tasks that require semantic understanding.

Your responsibilities:
- Translate Arabic titles and descriptions to English
- Infer property type from description when not explicitly stated
- Infer district from contextual clues when direct lookup fails
- Assess listing completeness (score 0.0-1.0)

Rules:
- Never convert currencies or areas — those are handled by other systems
- Return ONLY valid JSON matching the schema provided
- If translation is uncertain, preserve the original Arabic text
- Never hallucinate RERA numbers — only extract if clearly present"""

CLEANING_OUTPUT_SCHEMA: str = json.dumps(
    {
        "cleaned_items": [
            {
                "listing_id": "string",
                "title_en": "English title string",
                "inferred_property_type": "villa|apartment|compound|land|commercial|other",
                "inferred_district": "canonical district name or null",
                "completeness_score": 0.0,
            }
        ]
    },
    indent=2,
)


def build_cleaning_prompt(raw_listings: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build messages for the cleaning agent LLM call.

    The LLM handles ONLY semantic tasks — translation, type inference,
    district inference. All numeric normalization is handled
    deterministically in normalizer.py.

    Args:
        raw_listings: List of raw listing dicts needing semantic cleaning.

    Returns:
        Messages array for the LiteLLM call.
    """
    condensed = [
        {
            "listing_id": listing.get("listing_id"),
            "raw_title": listing.get("raw_title"),
            "raw_description": listing.get("raw_description"),
            "raw_location": listing.get("raw_location"),
            "raw_property_type": listing.get("raw_property_type"),
        }
        for listing in raw_listings
    ]

    user_content = f"""Process these {len(raw_listings)} listings.
For each listing perform ONLY these semantic tasks:
1. Translate raw_title to English (title_en)
2. Infer property type from title + description
3. Infer district if raw_location lookup failed (inferred_district)
4. Score completeness 0.0-1.0 based on data availability

Listings to process:
{json.dumps(condensed, ensure_ascii=False, indent=2)}

Return ONLY this JSON schema, no other text:
{CLEANING_OUTPUT_SCHEMA}"""

    return [
        {"role": "system", "content": CLEANING_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
