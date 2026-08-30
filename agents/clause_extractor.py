from models import Clause, ReviewState, TrajectoryEntry
from llm import call_with_tool

_TOOL = {
    "name": "extract_clauses",
    "description": "Extract and categorize all meaningful clauses from a contract.",
    "parameters": {
        "type": "object",
        "properties": {
            "clauses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id":          {"type": "string", "description": "Short unique ID e.g. cl_01"},
                        "clause_type": {"type": "string", "description": "Category: liability, ip_assignment, termination, confidentiality, governing_law, auto_renewal, amendment, data_processing, sla, indemnification, dispute_resolution, other"},
                        "text":        {"type": "string", "description": "Full verbatim clause text"},
                    },
                    "required": ["id", "clause_type", "text"],
                },
            }
        },
        "required": ["clauses"],
    },
}


def run(state: ReviewState) -> dict:
    result, tokens = call_with_tool(
        system="You are a legal contract analyst. Extract every meaningful clause and assign it a category. Include all clauses — both standard and potentially problematic.",
        messages=[{"role": "user", "content": f"Contract type: {state['contract_type']}\n\n---\n{state['contract_text']}\n---"}],
        tool=_TOOL,
    )

    clauses = [Clause(**c) for c in result.get("clauses", [])]

    return {
        "clauses": clauses,
        "trajectory": [TrajectoryEntry(
            agent="ClauseExtractorAgent",
            input_summary=f"Contract ({state['contract_type']}), {len(state['contract_text'])} chars",
            output_summary=f"Extracted {len(clauses)} clauses: {[c.clause_type for c in clauses]}",
            tokens_used=tokens,
        )],
    }
