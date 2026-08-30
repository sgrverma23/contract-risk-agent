from __future__ import annotations
import uuid
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from models import ReviewState, FlaggedClause, RiskLevel, TrajectoryEntry
import agents.clause_extractor as clause_extractor
import agents.risk_scorer as risk_scorer
import agents.template_comparator as template_comparator
import agents.missing_clause as missing_clause
import agents.synthesizer as synthesizer


def extract_node(state: ReviewState) -> dict:
    return clause_extractor.run(state)


def score_node(state: ReviewState) -> dict:
    return risk_scorer.run(state)


def compare_node(state: ReviewState) -> dict:
    return template_comparator.run(state)


def missing_node(state: ReviewState) -> dict:
    return missing_clause.run(state)


def human_review_node(state: ReviewState) -> dict:
    """Pause and surface all flags to the human reviewer."""
    review_payload = {
        "flagged_clauses": [f.model_dump() for f in state.get("flagged_clauses", [])],
        "missing_clauses": state.get("missing_clauses", []),
        "template_issues": [i.model_dump() for i in state.get("template_issues", [])],
    }

    # Execution pauses here until the caller resumes with human decisions
    human_response = interrupt(review_payload)

    approved_raw = human_response.get("approved_flags", [])
    approved: list[FlaggedClause] = []
    for item in approved_raw:
        item["risk_level"] = RiskLevel(item["risk_level"])
        approved.append(FlaggedClause(**item))

    entry = TrajectoryEntry(
        agent="HumanReviewCheckpoint",
        input_summary=f"Presented {len(review_payload['flagged_clauses'])} flags to reviewer",
        output_summary=(
            f"Reviewer approved {len(approved)} flags, "
            f"dismissed {len(review_payload['flagged_clauses']) - len(approved)}"
        ),
    )

    return {"human_approved": approved, "trajectory": [entry]}


def synthesize_node(state: ReviewState) -> dict:
    return synthesizer.run(state)


def build_graph():
    builder = StateGraph(ReviewState)

    builder.add_node("extract", extract_node)
    builder.add_node("score", score_node)
    builder.add_node("compare", compare_node)
    builder.add_node("missing", missing_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("synthesize", synthesize_node)

    builder.set_entry_point("extract")
    builder.add_edge("extract", "score")
    builder.add_edge("score", "compare")
    builder.add_edge("compare", "missing")
    builder.add_edge("missing", "human_review")
    builder.add_edge("human_review", "synthesize")
    builder.add_edge("synthesize", END)

    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


graph = build_graph()


def start_review(contract_text: str, contract_type: str) -> tuple[str, dict]:
    """Run the graph until the human checkpoint. Returns (session_id, pending_review_data)."""
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    initial_state: ReviewState = {
        "contract_text": contract_text,
        "contract_type": contract_type,
        "session_id": session_id,
        "clauses": [],
        "flagged_clauses": [],
        "missing_clauses": [],
        "template_issues": [],
        "human_approved": [],
        "final_brief": "",
        "trajectory": [],
    }

    result = graph.invoke(initial_state, config)
    # After interrupt, the graph returns the interrupted state value
    return session_id, result


def resume_review(session_id: str, approved_flags: list[dict]) -> dict:
    """Resume the graph with human decisions and return the final state."""
    config = {"configurable": {"thread_id": session_id}}
    final = graph.invoke(
        Command(resume={"approved_flags": approved_flags}),
        config,
    )
    return final
