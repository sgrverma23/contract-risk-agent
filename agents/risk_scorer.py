from models import FlaggedClause, RiskLevel, ReviewState, TrajectoryEntry
from llm import call_with_tool

_TOOL = {
    "name": "score_risk",
    "description": "Assess each clause for legal and commercial risk. Only include clauses rated caution or reject.",
    "parameters": {
        "type": "object",
        "properties": {
            "flagged_clauses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "clause_id":      {"type": "string"},
                        "clause_type":    {"type": "string"},
                        "clause_text":    {"type": "string"},
                        "risk_level":     {"type": "string", "enum": ["caution", "reject"]},
                        "reason":         {"type": "string", "description": "Why this clause is risky"},
                        "recommendation": {"type": "string", "description": "What to negotiate"},
                    },
                    "required": ["clause_id", "clause_type", "clause_text", "risk_level", "reason", "recommendation"],
                },
            }
        },
        "required": ["flagged_clauses"],
    },
}


def run(state: ReviewState) -> dict:
    clauses = state["clauses"]
    clauses_text = "\n\n".join(f"[{c.id} | {c.clause_type}]\n{c.text}" for c in clauses)

    result, tokens = call_with_tool(
        system=(
            "You are a senior commercial lawyer reviewing a contract on behalf of the party signing it. "
            "Flag every clause that is materially unfavorable, unusual, or missing standard protections. "
            "Only return clauses rated caution or reject — skip safe clauses."
        ),
        messages=[{"role": "user", "content": f"Contract type: {state['contract_type']}\n\nReview these clauses:\n\n{clauses_text}"}],
        tool=_TOOL,
    )

    flagged = []
    for item in result.get("flagged_clauses", []):
        item["risk_level"] = RiskLevel(item["risk_level"])
        flagged.append(FlaggedClause(**item))

    reject_count  = sum(1 for f in flagged if f.risk_level == RiskLevel.REJECT)
    caution_count = sum(1 for f in flagged if f.risk_level == RiskLevel.CAUTION)

    return {
        "flagged_clauses": flagged,
        "trajectory": [TrajectoryEntry(
            agent="RiskScorerAgent",
            input_summary=f"{len(clauses)} clauses reviewed",
            output_summary=f"Flagged {len(flagged)}: {reject_count} reject, {caution_count} caution",
            tokens_used=tokens,
        )],
    }
