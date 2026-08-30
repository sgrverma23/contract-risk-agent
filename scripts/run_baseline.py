"""
Run the single-prompt baseline on all test cases and save results.

Usage:
    python scripts/run_baseline.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from baseline.single_prompt import review

TEST_DIR = ROOT / "evaluation" / "test_cases"
RESULTS_DIR = ROOT / "evaluation" / "baseline_results"
RESULTS_DIR.mkdir(exist_ok=True)


def main():
    label_files = sorted(TEST_DIR.glob("*_labels.json"))
    if not label_files:
        print("No test cases found. Run: python scripts/generate_contracts.py")
        return

    for label_path in label_files:
        name = label_path.stem.replace("_labels", "")
        contract_path = TEST_DIR / f"{name}.txt"
        if not contract_path.exists():
            continue

        labels = json.loads(label_path.read_text())
        contract_text = contract_path.read_text()

        print(f"Running baseline on {name}...")
        result = review(contract_text, labels["contract_type"])

        output = {
            "case": name,
            "contract_type": labels["contract_type"],
            "review_text": result["review_text"],
            "tokens_used": result["tokens_used"],
            "model": result["model"],
        }

        (RESULTS_DIR / f"{name}_baseline.json").write_text(
            json.dumps(output, indent=2)
        )
        print(f"  → Saved ({result['tokens_used']} tokens)")

    print(f"\nDone. Results in {RESULTS_DIR}")


if __name__ == "__main__":
    main()
