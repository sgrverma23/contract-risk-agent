"""
Run the full comparative evaluation: agent vs baseline.

Usage:
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --mode agent
    python scripts/run_evaluation.py --mode baseline
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from evaluation.evaluator import (
    run_agent_evaluation,
    run_baseline_evaluation,
    print_results,
)
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["agent", "baseline", "both"], default="both")
    args = parser.parse_args()

    baseline_summary = None
    agent_summary = None

    if args.mode in ("baseline", "both"):
        print("\nRunning baseline evaluation...")
        baseline_results = run_baseline_evaluation()
        baseline_summary = print_results(baseline_results, "BASELINE (Single Prompt)")

    if args.mode in ("agent", "both"):
        print("\nRunning agent evaluation...")
        agent_results = run_agent_evaluation()
        agent_summary = print_results(agent_results, "AGENT SOLUTION")

    if args.mode == "both" and baseline_summary and agent_summary:
        print(f"\n{'='*60}")
        print("  IMPROVEMENT SUMMARY")
        print(f"{'='*60}")
        print(f"  {'Metric':<14} {'Baseline':>9} {'Agent':>9} {'Change':>9}")
        print(f"  {'-'*48}")
        for metric in ("avg_recall", "avg_precision", "avg_f1"):
            b = baseline_summary[metric]
            a = agent_summary[metric]
            delta = a - b
            sign = "+" if delta >= 0 else ""
            label = metric.replace("avg_", "").title()
            print(f"  {label:<14} {b:>9.3f} {a:>9.3f} {sign}{delta:>8.3f}")
