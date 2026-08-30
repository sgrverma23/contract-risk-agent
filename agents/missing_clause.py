from models import ReviewState, TrajectoryEntry
from llm import call_with_tool

_REQUIRED = {
    "nda": [
        "confidentiality_obligations", "definition_of_confidential_information",
        "exclusions_from_confidentiality", "term_and_expiration",
        "return_or_destruction_of_information", "limitation_of_liability",
        "governing_law", "mutual_obligations",
    ],
    "saas_msa": [
        "limitation_of_liability", "indemnification", "data_processing_agreement",
        "service_level_agreement", "termination_for_convenience", "ip_ownership",
        "confidentiality", "governing_law", "dispute_resolution", "auto_renewal_notice",
    ],
}

_TOOL = {
    "name": "check_missing",
    "description": "Identify required clauses that are absent from the contract.",
    "parameters": {
        "type": "object",
        "properties": {
            "missing_clauses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Required clause types that are absent",
            }
        },
        "required": ["missing_clauses"],
    },
}


def run(state: ReviewState) -> dict:
    required = _REQUIRED.get(state["contract_type"], [])
    present  = ", ".join(sorted({c.clause_type for c in state["clauses"]}))

    result, tokens = call_with_tool(
        system="You are a contract compliance checker. Identify which required clauses are genuinely absent. Be strict — only mark missing if no clause covers that topic.",
        messages=[{"role": "user", "content": f"Contract type: {state['contract_type']}\nRequired: {required}\nPresent: {present}\n\nWhich required clauses are missing?"}],
        tool=_TOOL,
        max_tokens=1024,
    )

    missing = result.get("missing_clauses", [])

    return {
        "missing_clauses": missing,
        "trajectory": [TrajectoryEntry(
            agent="MissingClauseAgent",
            input_summary=f"{len(required)} required, {len(present.split(','))} present",
            output_summary=f"Missing: {missing}",
            tokens_used=tokens,
        )],
    }
