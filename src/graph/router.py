"""Defines conditional routing logic between graph nodes."""

from __future__ import annotations

from src.core.logging_setup import get_logger
from src.core.state import AgentState

logger = get_logger(__name__)


def route_after_sourcing(state: AgentState) -> str:
    """Route after the sourcing node completes.

    Args:
        state: Current pipeline state.

    Returns:
        "cleaning_agent" if raw_listings exist and sourcing succeeded.
        "error_node" if sourcing failed or produced no listings.
    """
    if state.current_phase == "sourcing_failed":
        logger.error("Routing to error: sourcing failed")
        return "error_node"
    if not state.raw_listings:
        logger.warning("Routing to error: no listings sourced")
        return "error_node"
    logger.info(f"Routing to cleaning: {len(state.raw_listings)} raw listings")
    return "cleaning_agent"


def route_after_cleaning(state: AgentState) -> str:
    """Route after the cleaning node completes.

    Args:
        state: Current pipeline state.

    Returns:
        "analyst_agent" always, unless cleaning itself failed —
        partial or empty cleaned_listings (e.g. sparse live data
        with no price/area) still produce a graceful report.
        "error_node" only if cleaning explicitly failed.
    """
    if state.current_phase == "cleaning_failed":
        logger.error("Routing to error: cleaning failed")
        return "error_node"

    if not state.cleaned_listings:
        logger.warning(
            "No cleaned listings — likely sparse live data. "
            "Routing to analyst with empty state for graceful report."
        )
        return "analyst_agent"

    logger.info(
        "Routing to analyst",
        extra={"cleaned_count": len(state.cleaned_listings)}
    )
    return "analyst_agent"


def route_after_analysis(state: AgentState) -> str:
    """Route after the analyst node completes.

    Args:
        state: Current pipeline state.

    Returns:
        "risk_agent" always — risk runs even if no undervalued listings
        were found. "error_node" only if analysis explicitly failed.
    """
    if state.current_phase == "analysis_failed":
        logger.error("Routing to error: analysis failed")
        return "error_node"
    logger.info("Routing to risk agent")
    return "risk_agent"


def route_after_risk(state: AgentState) -> str:
    """Route after the risk node completes.

    Args:
        state: Current pipeline state.

    Returns:
        "report_node" always — risk is the final agent before reporting.
        "error_node" only if risk assessment explicitly failed.
    """
    if state.current_phase == "risk_failed":
        logger.error("Routing to error: risk assessment failed")
        return "error_node"
    logger.info("Routing to report node")
    return "report_node"
