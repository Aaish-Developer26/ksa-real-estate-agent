"""Builds the LangGraph multi-agent subgraph pipeline."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.analyst.agent import analyst_node
from src.agents.cleaning.agent import cleaning_node
from src.agents.risk.agent import risk_node
from src.agents.sourcing.agent import sourcing_node
from src.core.logging_setup import get_logger
from src.core.state import AgentState
from src.graph.checkpointer import get_checkpointer
from src.graph.router import (
    route_after_analysis,
    route_after_cleaning,
    route_after_risk,
    route_after_sourcing,
)

logger = get_logger(__name__)


async def report_node(state: AgentState) -> dict[str, Any]:
    """Assemble the final investment report from all agent outputs.

    Combines analysis_summary, compliance_report, and top undervalued
    listings into a single structured investment report string.

    Args:
        state: Fully populated AgentState after all agents complete.

    Returns:
        State update with investment_report and current_phase="complete".
    """
    benchmarks_block = "\n".join(
        f"  {district}: {value:,.0f}"
        for district, value in state.district_benchmarks.items()
    )
    report = f"""
═══════════════════════════════════════════════════
RIYADH REAL ESTATE INVESTMENT INTELLIGENCE REPORT
Run ID: {state.run_id}
Generated: {state.created_at}
═══════════════════════════════════════════════════

MARKET ANALYSIS
───────────────
{state.analysis_summary}

DISTRICT BENCHMARKS (SAR/m²)
─────────────────────────────
{benchmarks_block}

INVESTMENT OPPORTUNITIES
────────────────────────
Undervalued listings identified: {len(state.undervalued_listing_ids)}
Listing IDs: {', '.join(state.undervalued_listing_ids) or 'None'}

COMPLIANCE SUMMARY
──────────────────
{state.compliance_report}

TOTAL LISTINGS PROCESSED: {len(state.cleaned_listings)}
═══════════════════════════════════════════════════
"""
    return {"investment_report": report.strip(), "current_phase": "complete"}


async def error_node(state: AgentState) -> dict[str, Any]:
    """Handle pipeline errors gracefully.

    Logs all accumulated errors and returns a failure report.

    Args:
        state: Pipeline state at the point of failure.

    Returns:
        State update with a failure investment_report and
        current_phase="failed".
    """
    logger.error(
        "Pipeline error node reached",
        extra={
            "run_id": state.run_id,
            "errors": state.errors,
            "phase": state.current_phase,
        },
    )
    return {
        "investment_report": (
            f"Pipeline failed at phase: {state.current_phase}\n"
            f"Errors: {state.errors}"
        ),
        "current_phase": "failed",
    }


def build_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    """Assemble and compile the full LangGraph agent pipeline.

    Builds a StateGraph with 6 nodes (4 agents + report + error)
    connected by conditional edges via router functions.

    Returns:
        Compiled LangGraph ready for invocation.
    """
    graph: StateGraph[AgentState, Any, Any, Any] = StateGraph(AgentState)

    graph.add_node("sourcing_agent", sourcing_node)
    graph.add_node("cleaning_agent", cleaning_node)
    graph.add_node("analyst_agent", analyst_node)
    graph.add_node("risk_agent", risk_node)
    graph.add_node("report_node", report_node)
    graph.add_node("error_node", error_node)

    graph.set_entry_point("sourcing_agent")

    graph.add_conditional_edges(
        "sourcing_agent",
        route_after_sourcing,
        {"cleaning_agent": "cleaning_agent", "error_node": "error_node"},
    )
    graph.add_conditional_edges(
        "cleaning_agent",
        route_after_cleaning,
        {"analyst_agent": "analyst_agent", "error_node": "error_node"},
    )
    graph.add_conditional_edges(
        "analyst_agent",
        route_after_analysis,
        {"risk_agent": "risk_agent", "error_node": "error_node"},
    )
    graph.add_conditional_edges(
        "risk_agent",
        route_after_risk,
        {"report_node": "report_node", "error_node": "error_node"},
    )

    graph.add_edge("report_node", END)
    graph.add_edge("error_node", END)

    checkpointer = get_checkpointer()
    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("LangGraph pipeline compiled successfully")
    return compiled
