from models import ReviewState, TrajectoryEntry, RiskLevel
from llm import call

def _overall_risk(state: ReviewState) -> str:
    approved = state.get("human_approved", [])
    if any(f.risk_level == RiskLevel.REJECT for f in approved):
        return "HIGH"
    if any(f.risk_level == RiskLevel.CAUTION for f in approved) or state.get("missing_clauses"):
        return "MEDIUM"
    return "LOW"


def run(state: ReviewState) -> dict:
    approved       = state.get("human_approved", [])
    missing        = state.get("missing_clauses", [])
    template_issues = state.get("template_issues", [])
    risk           = _overall_risk(state)

    flags_text = "\n".join(
        f"- [{f.risk_level.upper()}] {f.clause_type}: {f.reason} → {f.recommendation}"
        + (f"\n  Reviewer note: {f.reviewer_note}" if f.reviewer_note else "")
        for f in approved
    ) or "None"

    missing_text   = "\n".join(f"- {m}" for m in missing) or "None"
    template_text  = "\n".join(f"- {i.issue_type.upper()} [{i.clause_type}]: {i.description}" for i in template_issues) or "None"

    prompt = f"""Write a professional contract risk assessment report in Markdown.

Contract type: {state['contract_type'].upper()}
Overall risk level: {risk}

APPROVED FLAGS (confirmed by human reviewer):
{flags_text}

MISSING REQUIRED CLAUSES:
{missing_text}

TEMPLATE DEVIATIONS:
{template_text}

Include:
1. Executive Summary (2–3 sentences, overall risk level, top concern)
2. Critical Issues (REJECT-level flags with specific clause citations)
3. Items for Negotiation (CAUTION-level flags)
4. Missing Clauses
5. Recommended Next Steps (3–5 concrete actions)

Write clearly and professionally. Cite specific clause types for each issue."""

    brief, tokens = call(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
    )

    return {
        "final_brief": brief,
        "trajectory": [TrajectoryEntry(
            agent="SynthesizerAgent",
            input_summary=f"{len(approved)} approved flags, {len(missing)} missing, {len(template_issues)} template issues",
            output_summary=f"Generated {len(brief)} char brief, risk={risk}",
            tokens_used=tokens,
        )],
    }
