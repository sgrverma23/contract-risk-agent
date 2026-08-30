from pathlib import Path
from models import TemplateIssue, ReviewState, TrajectoryEntry
from llm import call_with_tool

_TEMPLATES_DIR = Path(__file__).parent.parent / "data" / "templates"

_TOOL = {
    "name": "compare_template",
    "description": "Identify deviations from standard template language.",
    "parameters": {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "issue_type":       {"type": "string", "enum": ["deviation", "missing"]},
                        "clause_type":      {"type": "string"},
                        "description":      {"type": "string"},
                        "standard_language": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "actual_language":   {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    },
                    "required": ["issue_type", "clause_type", "description"],
                },
            }
        },
        "required": ["issues"],
    },
}


def run(state: ReviewState) -> dict:
    template_path = _TEMPLATES_DIR / f"{state['contract_type']}_template.txt"
    if not template_path.exists():
        return {
            "template_issues": [],
            "trajectory": [TrajectoryEntry(
                agent="TemplateComparatorAgent",
                input_summary=f"No template for {state['contract_type']}",
                output_summary="Skipped",
            )],
        }

    template = template_path.read_text()
    clauses_text = "\n\n".join(f"[{c.id} | {c.clause_type}]\n{c.text}" for c in state["clauses"])

    result, tokens = call_with_tool(
        system="You are a contract specialist. You MUST call the compare_template function to return your findings. Do not write prose — only use the function. Keep standard_language and actual_language fields SHORT (max 30 words each) — summarize, do not quote verbatim.",
        messages=[{"role": "user", "content": f"Compare these contract clauses against the reference template. Call compare_template with your findings.\n\nREFERENCE TEMPLATE:\n{template}\n\nSUBMITTED CONTRACT CLAUSES:\n{clauses_text}"}],
        tool=_TOOL,
        max_tokens=4096,
    )

    issues = [TemplateIssue(**i) for i in result.get("issues", [])]

    return {
        "template_issues": issues,
        "trajectory": [TrajectoryEntry(
            agent="TemplateComparatorAgent",
            input_summary=f"{len(state['clauses'])} clauses vs {state['contract_type']} template",
            output_summary=f"Found {len(issues)} template deviations",
            tokens_used=tokens,
        )],
    }
