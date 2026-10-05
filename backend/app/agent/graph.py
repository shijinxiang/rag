"""
=============================================================================
LangGraph Agent — Graph definition and compilation
=============================================================================

Defines the agent's state graph with nodes and edges:

    classify → retrieve → generate → review → end
    classify → generate (general_chat, no retrieval)
    classify → review → generate (document_operation)
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    classify_node,
    generate_node,
    retrieve_node,
    review_node,
    route_after_classify,
    route_after_retrieve,
    route_after_review,
    tool_node,
)
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def build_agent_graph() -> StateGraph:
    """Build and compile the LangGraph agent.

    Returns:
        A compiled ``StateGraph`` ready for async invocation.
    """
    builder = StateGraph(AgentState)

    # ---- Register nodes ----
    builder.add_node("classify", classify_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)
    builder.add_node("review", review_node)
    builder.add_node("tools", tool_node)

    # ---- Edges ----
    builder.add_edge(START, "classify")

    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "retrieve": "retrieve",
            "generate": "generate",
            "review": "review",
            "tools": "tools",
        },
    )

    builder.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "tools": "tools",
            "generate": "generate",
        },
    )
    builder.add_edge("tools", "generate")

    builder.add_conditional_edges(
        "review",
        route_after_review,
        {
            "generate": "generate",
            "tools": "tools",
            "__end__": END,
        },
    )

    builder.add_edge("generate", END)

    # ---- Compile ----
    graph = builder.compile()
    logger.info("LangGraph agent compiled successfully.")
    return graph


# Singleton
_agent_graph: StateGraph | None = None


def get_agent_graph() -> StateGraph:
    """Return the global agent graph singleton."""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph
