"""
Baseline: single-prompt contract review with no agent architecture.
Used for fair comparison against the multi-agent solution.
"""

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from llm import call

PROMPT_TEMPLATE = """You are a legal contract reviewer. Review the following {contract_type} for red flags, risky clauses, and missing standard protections.

For each issue found, state:
- The clause type
- Why it is problematic
- What should be negotiated or added

Contract:
---
{contract_text}
---

Provide your review as a structured list."""


def review(contract_text: str, contract_type: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        contract_type=contract_type,
        contract_text=contract_text,
    )

    text, tokens = call(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
    )

    return {
        "review_text": text,
        "tokens_used": tokens,
    }
