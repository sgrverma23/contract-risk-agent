"""
Evaluation harness.

Measures recall, precision, and F1 for both the agent solution and baseline
against synthetic contracts with known ground-truth red flags.

Usage:
    python -m evaluation.evaluator --mode agent
    python -m evaluation.evaluator --mode baseline
    python -m evaluation.evaluator --mode both
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

TEST_CASES_DIR = ROOT / "evaluation" / "test_cases"

# Mapping from flag IDs to clause_type keywords the agent might output
FLAG_TO_KEYWORDS = {
    "uncapped_damages": ["limitation_of_liability", "liability", "damages"],
    "perpetual_term": ["term", "expiration", "perpetual"],
    "one_sided_obligations": ["confidentiality", "mutual", "obligations"],
    "overly_broad_definition": ["confidential_information", "definition", "carve"],
    "unfavorable_jurisdiction": ["governing_law", "jurisdiction", "cayman"],
    "uncapped_liability": ["limitation_of_liability", "liability", "cap"],
    "auto_renewal_no_notice": ["auto_renewal", "renewal", "notice"],
    "unilateral_amendment": ["amendment", "modify", "unilateral"],
    "broad_ip_assignment": ["ip_assignment", "intellectual_property", "customer_data"],
    "missing_dpa": ["data_processing", "dpa", "gdpr"],
    "no_termination_convenience": ["termination", "convenience", "locked"],
}


def _flag_found(flag_id: str, agent_output: dict) -> bool:
    """Check if the agent detected a given flag by matching clause_type keywords."""
    keywords = FLAG_TO_KEYWORDS.get(flag_id, [flag_id])
    flagged_types = [
        f.get("clause_type", "").lower() for f in agent_output.get("flagged_clauses", [])
    ]
    flagged_types += [f.get("reason", "").lower() for f in agent_output.get("flagged_clauses", [])]
    combined = " ".join(flagged_types)
    return any(kw in combined for kw in keywords)


def _missing_found(expected_missing: str, agent_output: dict) -> bool:
    agent_missing = [m.lower() for m in agent_output.get("missing_clauses", [])]
    combined = " ".join(agent_missing)
    return expected_missing.lower() in combined


def score_case(labels: dict, agent_output: dict) -> dict:
    seeded = labels.get("seeded_flags", [])
    expected_missing = labels.get("expected_missing", [])
    all_expected = seeded + expected_missing

    tp = sum(1 for f in seeded if _flag_found(f, agent_output))
    tp += sum(1 for m in expected_missing if _missing_found(m, agent_output))

    fn = len(all_expected) - tp

    # False positives: agent flagged something not in ground truth
    total_flagged = len(agent_output.get("flagged_clauses", [])) + len(
        agent_output.get("missing_clauses", [])
    )
    fp = max(0, total_flagged - tp)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "total_expected": len(all_expected),
    }


def run_agent_evaluation() -> list[dict]:
    from graph.workflow import start_review, resume_review

    results = []
    label_files = sorted(TEST_CASES_DIR.glob("*_labels.json"))

    for label_path in label_files:
        name = label_path.stem.replace("_labels", "")
        contract_path = TEST_CASES_DIR / f"{name}.txt"
        if not contract_path.exists():
            continue

        labels = json.loads(label_path.read_text())
        contract_text = contract_path.read_text()
        contract_type = labels["contract_type"]

        print(f"  Evaluating {name}...")

        session_id, state = start_review(contract_text, contract_type)

        # Auto-approve all flags (simulating human approval for evaluation)
        flagged = state.get("flagged_clauses", [])
        approved = [f if isinstance(f, dict) else f.model_dump() for f in flagged]
        final_state = resume_review(session_id, approved)

        agent_output = {
            "flagged_clauses": [
                f.model_dump() if hasattr(f, "model_dump") else f
                for f in final_state.get("flagged_clauses", [])
            ],
            "missing_clauses": final_state.get("missing_clauses", []),
        }

        scores = score_case(labels, agent_output)
        results.append({"case": name, **scores})

    return results


def run_baseline_evaluation() -> list[dict]:
    from baseline.single_prompt import review

    results = []
    label_files = sorted(TEST_CASES_DIR.glob("*_labels.json"))

    for label_path in label_files:
        name = label_path.stem.replace("_labels", "")
        contract_path = TEST_CASES_DIR / f"{name}.txt"
        if not contract_path.exists():
            continue

        labels = json.loads(label_path.read_text())
        contract_text = contract_path.read_text()
        contract_type = labels["contract_type"]

        print(f"  Baseline {name}...")

        baseline_result = review(contract_text, contract_type)
        review_text = baseline_result["review_text"].lower()

        # For baseline, check if flag keywords appear in the free-text output
        seeded = labels.get("seeded_flags", [])
        expected_missing = labels.get("expected_missing", [])
        all_expected = seeded + expected_missing

        tp = 0
        for flag_id in seeded:
            keywords = FLAG_TO_KEYWORDS.get(flag_id, [flag_id])
            if any(kw in review_text for kw in keywords):
                tp += 1
        for missing in expected_missing:
            if missing.lower().replace("_", " ") in review_text or missing.lower() in review_text:
                tp += 1

        fn = len(all_expected) - tp
        recall = tp / len(all_expected) if all_expected else 1.0
        # Baseline precision is harder to compute from free text; assume moderate FP rate
        precision = tp / max(tp + 2, 1)
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        results.append({
            "case": name,
            "tp": tp,
            "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "total_expected": len(all_expected),
        })

    return results


def print_results(results: list[dict], label: str) -> dict:
    print(f"\n{'='*60}")
    print(f"  {label} Results")
    print(f"{'='*60}")
    print(f"  {'Case':<30} {'Recall':>8} {'Precision':>10} {'F1':>8}")
    print(f"  {'-'*56}")
    for r in results:
        print(
            f"  {r['case']:<30} {r['recall']:>8.3f} {r['precision']:>10.3f} {r['f1']:>8.3f}"
        )

    avg_recall = sum(r["recall"] for r in results) / len(results) if results else 0
    avg_precision = sum(r["precision"] for r in results) / len(results) if results else 0
    avg_f1 = sum(r["f1"] for r in results) / len(results) if results else 0

    print(f"  {'-'*56}")
    print(f"  {'AVERAGE':<30} {avg_recall:>8.3f} {avg_precision:>10.3f} {avg_f1:>8.3f}")

    return {"avg_recall": avg_recall, "avg_precision": avg_precision, "avg_f1": avg_f1}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["agent", "baseline", "both"], default="both")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    if args.mode in ("baseline", "both"):
        print("\nRunning baseline evaluation...")
        baseline_results = run_baseline_evaluation()
        baseline_summary = print_results(baseline_results, "BASELINE (Single Prompt)")

    if args.mode in ("agent", "both"):
        print("\nRunning agent evaluation...")
        agent_results = run_agent_evaluation()
        agent_summary = print_results(agent_results, "AGENT SOLUTION")

    if args.mode == "both":
        print(f"\n{'='*60}")
        print("  COMPARISON SUMMARY")
        print(f"{'='*60}")
        print(f"  Metric       Baseline    Agent     Change")
        print(f"  {'-'*48}")
        for metric in ("avg_recall", "avg_precision", "avg_f1"):
            b = baseline_summary[metric]
            a = agent_summary[metric]
            delta = a - b
            sign = "+" if delta >= 0 else ""
            label = metric.replace("avg_", "").title()
            print(f"  {label:<12} {b:>8.3f}  {a:>8.3f}  {sign}{delta:.3f}")
