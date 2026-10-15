from langgraph.graph import END, StateGraph

from src.agents.nodes.example_node import analyze_node, respond_node
from src.agents.state import AgentState


def should_continue(state: AgentState) -> str:
    """Route based on whether an error occurred during analysis."""
    if state.get("error"):
        return END
    return "respond"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("analyze", analyze_node)
    graph.add_node("respond", respond_node)

    # Add edges
    graph.set_entry_point("analyze")
    # Keep every routing value explicit so graph behavior remains stable as
    # more analysis branches are added.
    graph.add_conditional_edges(
        "analyze",
        should_continue,
        {"respond": "respond", END: END},
    )
    graph.add_edge("respond", END)

    return graph.compile()


agent = build_graph()
