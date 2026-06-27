"""Implements the Risk and Compliance Agent responsible for regulatory flagging."""

from __future__ import annotations

import json
from typing import Any

from src.core.config import get_settings
from src.core.logging_setup import get_logger
from src.core.state import AgentState, ComplianceFlag
from src.tools.compliance_tools import run_all_compliance_checks

logger = get_logger(__name__)


async def risk_node(state: AgentState) -> dict[str, Any]:
    """Execute the Risk and Compliance Agent node.

    Uses deterministic compliance_tools.py for all flag generation.
    LLM is used only for the final narrative summary (not flag logic).

    Args:
        state: AgentState with cleaned_listings and district_benchmarks.

    Returns:
        Partial state update with compliance_flags and compliance_report.
    """
    if not state.cleaned_listings:
        logger.warning("No cleaned listings for risk assessment")
        return {
            "current_phase": "risk_complete",
            "compliance_flags": [],
            "compliance_report": "No listings to assess.",
        }

    logger.info(
        "Risk agent started",
        extra={
            "run_id": state.run_id,
            "listing_count": len(state.cleaned_listings),
        },
    )

    # Run deterministic compliance checks — compliance rules are
    # deterministic and should never be delegated to an LLM for generation
    all_flag_dicts: list[dict[str, Any]] = []

    for listing in state.cleaned_listings:
        flag_dicts = run_all_compliance_checks(
            listing_id=listing.listing_id,
            rera_number=listing.rera_number,
            is_waqf=listing.is_waqf,
            district=listing.district,
            property_type=listing.property_type,
            is_foreign_ownership_restricted=(
                listing.is_foreign_ownership_restricted
            ),
        )
        all_flag_dicts.extend(flag_dicts)

    logger.info(
        "Deterministic compliance checks complete",
        extra={
            "total_flags": len(all_flag_dicts),
            "listings_checked": len(state.cleaned_listings),
        },
    )

    compliance_flags: list[ComplianceFlag] = []
    for flag_dict in all_flag_dicts:
        try:
            compliance_flags.append(ComplianceFlag(**flag_dict))
        except Exception as exc:
            logger.warning(
                "Invalid compliance flag — skipping",
                extra={"flag": flag_dict, "error": str(exc)},
            )

    critical = [f for f in compliance_flags if f.severity == "critical"]
    high = [f for f in compliance_flags if f.severity == "high"]
    medium = [f for f in compliance_flags if f.severity == "medium"]
    low = [f for f in compliance_flags if f.severity == "low"]

    # LLM is used only for the short narrative summary — small prompt,
    # no tool calls, just a paragraph of text
    settings = get_settings()
    compliance_report = ""

    flag_summary_for_llm = {
        "total_listings": len(state.cleaned_listings),
        "total_flags": len(compliance_flags),
        "critical_count": len(critical),
        "high_count": len(high),
        "medium_count": len(medium),
        "low_count": len(low),
        "critical_issues": [
            {"listing_id": f.listing_id, "type": f.flag_type}
            for f in critical[:5]
        ],
        "high_issues": [
            {"listing_id": f.listing_id, "type": f.flag_type} for f in high[:5]
        ],
    }

    try:
        import litellm

        narrative_messages = [
            {
                "role": "system",
                "content": (
                    "You are a Saudi real estate compliance specialist. "
                    "Write a concise 3-5 sentence compliance summary. "
                    "Be direct and professional. No bullet points."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write a compliance summary for this assessment:\n"
                    f"{json.dumps(flag_summary_for_llm, indent=2)}\n\n"
                    f"Districts analyzed: "
                    f"{list(state.district_benchmarks.keys())}\n"
                    f"End with a clear PROCEED / CAUTION / DO NOT PROCEED "
                    f"recommendation."
                ),
            },
        ]

        narrative_response = await litellm.acompletion(
            model=settings.litellm_model,
            messages=narrative_messages,
            temperature=0.2,
            max_tokens=300,
        )
        compliance_report = (
            narrative_response.choices[0].message.content or ""
        ).strip()

    except Exception as exc:
        logger.warning(
            "LLM narrative failed — using deterministic report",
            extra={"error": str(exc)},
        )
        recommendation = (
            "DO NOT PROCEED"
            if critical
            else "PROCEED WITH CAUTION"
            if high
            else "CLEAR TO PROCEED"
        )
        compliance_report = (
            f"Compliance assessment of {len(state.cleaned_listings)} "
            f"listings identified {len(compliance_flags)} flags: "
            f"{len(critical)} critical, {len(high)} high, "
            f"{len(medium)} medium, {len(low)} low severity. "
            f"Critical issues include missing RERA registrations "
            f"and Waqf property flags. "
            f"Recommendation: {recommendation}."
        )

    critical_desc = (
        [f.description for f in critical[:3]] if critical else ["None"]
    )
    final_report = (
        f"Compliance Assessment — Run {state.run_id}\n"
        f"Total listings assessed: {len(state.cleaned_listings)}\n"
        f"Compliance flags raised: {len(compliance_flags)}\n"
        f"Critical: {len(critical)} | High: {len(high)} | "
        f"Medium: {len(medium)} | Low: {len(low)}\n\n"
        f"Critical issues: {critical_desc}\n\n"
        f"{compliance_report}"
    )

    logger.info(
        "Risk agent complete",
        extra={
            "run_id": state.run_id,
            "flags": len(compliance_flags),
            "critical": len(critical),
        },
    )

    return {
        "compliance_flags": compliance_flags,
        "compliance_report": final_report,
        "current_phase": "risk_complete",
    }
