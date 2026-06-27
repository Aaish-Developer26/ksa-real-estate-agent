"""Prompt templates and tool schemas for the Risk & Compliance Agent."""

from __future__ import annotations

import json
from typing import Any

RISK_SYSTEM_PROMPT: str = """You are a Saudi real estate regulatory compliance and risk
assessment specialist. You evaluate listings against RERA
requirements, ownership restrictions, and fraud indicators.

Compliance rules you enforce:
- RERA: All listings must have a valid 10-digit RERA number
- Waqf: Islamic endowment properties cannot be sold — flag CRITICAL
- Foreign ownership: Non-GCC nationals restricted to approved zones
  Approved expat zones in Riyadh: KAFD, Diplomatic Quarter (DQ)
- VAT: Commercial properties subject to 15% VAT — flag for buyer
- Price outliers: Listings >3 standard deviations from district mean
  may indicate fraud or data tampering — flag HIGH severity

Output format: return ONLY a JSON array of compliance flag objects."""

RISK_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "insert_compliance_flags",
            "description": "Insert compliance flags for listings",
            "parameters": {
                "type": "object",
                "properties": {
                    "flags": {"type": "array", "items": {"type": "object"}},
                    "run_id": {"type": "string"},
                },
                "required": ["flags", "run_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_analysis_run",
            "description": "Update analysis run status and completion summary",
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "status": {"type": "string"},
                    "summary": {"type": "string"},
                    "total_listings": {"type": "integer"},
                },
                "required": ["run_id", "status"],
            },
        },
    },
]


def build_risk_prompt(
    cleaned_listings: list[dict[str, Any]],
    district_benchmarks: dict[str, float],
    run_id: str,
) -> list[dict[str, str]]:
    """Build messages for the risk agent LLM call.

    Includes district benchmarks so the agent can compute price
    deviation without needing additional tool calls.

    Args:
        cleaned_listings: Normalized listings to assess.
        district_benchmarks: Avg price/sqm per district from the analyst.
        run_id: Current pipeline run ID for flag records.

    Returns:
        Messages array for the LiteLLM call.
    """
    user_content = f"""Assess these {len(cleaned_listings)} cleaned Riyadh
real estate listings for compliance and risk (run_id={run_id}).

District price/sqm benchmarks (for outlier detection):
{json.dumps(district_benchmarks, indent=2)}

Listings:
{json.dumps(cleaned_listings, ensure_ascii=False, indent=2, default=str)}

For each compliance issue found, output a flag object with exactly
these fields: listing_id, flag_type, severity, description, flagged_at.

flag_type must be one of: missing_rera, waqf_property,
foreign_ownership_restricted, price_outlier, area_outlier, vat_applicable.
severity must be one of: low, medium, high, critical.

Return ONLY a JSON array of flag objects, no other text."""

    return [
        {"role": "system", "content": RISK_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
