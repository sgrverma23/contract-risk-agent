"""
Generate synthetic test contracts with known red flags for evaluation.
Produces contracts in evaluation/test_cases/ with ground-truth label files.

Usage:
    python scripts/generate_contracts.py
"""

import json
import random
from pathlib import Path

ROOT = Path(__file__).parent.parent
CATALOG_PATH = ROOT / "data" / "red_flag_catalog.json"
TEMPLATES_DIR = ROOT / "data" / "templates"
OUTPUT_DIR = ROOT / "evaluation" / "test_cases"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CLEAN_NDA = """MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement ("Agreement") is entered into as of the Effective Date between the parties.

1. DEFINITION OF CONFIDENTIAL INFORMATION
"Confidential Information" means any non-public information disclosed by either party that is designated as confidential or that reasonably should be understood to be confidential. This excludes information that is publicly known, independently developed, or required to be disclosed by law.

2. CONFIDENTIALITY OBLIGATIONS
Each party shall hold Confidential Information in strict confidence using no less than reasonable care, shall not disclose it to third parties without prior written consent, and shall use it solely for evaluating a potential business relationship.

3. TERM
This Agreement commences on the Effective Date and continues for two (2) years. Confidentiality obligations survive for three (3) years after termination.

4. RETURN OF INFORMATION
Upon request or termination, each party shall return or destroy all Confidential Information and confirm in writing within ten (10) business days.

5. LIMITATION OF LIABILITY
NEITHER PARTY SHALL BE LIABLE FOR INDIRECT OR CONSEQUENTIAL DAMAGES. TOTAL LIABILITY SHALL NOT EXCEED $50,000.

6. GOVERNING LAW
This Agreement is governed by the laws of the State of Delaware. Disputes shall be resolved by arbitration in Delaware under AAA rules.
"""

CLEAN_SAAS_MSA = """SAAS MASTER SERVICES AGREEMENT

1. LICENSE
Vendor grants Customer a limited, non-exclusive license to access the Services for internal business purposes during the Subscription Term.

2. SERVICE LEVEL AGREEMENT
Vendor guarantees 99.5% monthly uptime. Downtime exceeding this threshold entitles Customer to service credits of 10% of monthly fees per additional 1%, capped at 30%.

3. DATA PROCESSING
Vendor processes Customer Data only per Customer's instructions, implements appropriate security measures, notifies of breaches within 72 hours, and deletes all data within 30 days of termination.

4. INTELLECTUAL PROPERTY
Customer owns all Customer Data. Vendor retains all rights to the Services and improvements.

5. LIMITATION OF LIABILITY
EACH PARTY'S LIABILITY IS CAPPED AT FEES PAID IN THE PRIOR TWELVE MONTHS. NEITHER PARTY IS LIABLE FOR INDIRECT OR CONSEQUENTIAL DAMAGES.

6. INDEMNIFICATION
Each party indemnifies the other against third-party claims arising from breach, gross negligence, or willful misconduct.

7. TERM AND TERMINATION
Initial term: twelve (12) months, auto-renewing with sixty (60) days notice. Either party may terminate for convenience on thirty (30) days notice.

8. AMENDMENTS
Amendments require written agreement signed by both parties.

9. GOVERNING LAW
Governed by Delaware law. Disputes resolved by arbitration in Delaware.
"""


def inject_flag(base_text: str, flag: dict) -> str:
    if flag["inject_text"] is None:
        # "missing" flag — nothing to inject, we just mark it in labels
        return base_text
    # Replace the relevant section with the flagged language
    return base_text + f"\n\n[AMENDED CLAUSE — {flag['clause_type'].upper()}]\n{flag['inject_text']}\n"


def generate_test_cases(catalog: dict, count: int = 5) -> None:
    cases_generated = 0

    for contract_type, flags_catalog in catalog.items():
        base = CLEAN_NDA if contract_type == "nda" else CLEAN_SAAS_MSA
        all_flags = flags_catalog

        # Case 1: Completely clean contract
        labels = {"contract_type": contract_type, "seeded_flags": [], "expected_missing": []}
        _write_case(f"{contract_type}_clean", base, labels)

        # Cases 2–N: 1 to 3 injected flags each
        random.seed(42)
        for i in range(1, count):
            n_flags = min(i, len(all_flags))
            chosen = random.sample(all_flags, n_flags)
            text = base
            seeded = []
            missing = []
            for flag in chosen:
                text = inject_flag(text, flag)
                if flag["inject_text"] is None:
                    missing.append(flag["clause_type"])
                else:
                    seeded.append(flag["id"])

            labels = {
                "contract_type": contract_type,
                "seeded_flags": seeded,
                "expected_missing": missing,
            }
            _write_case(f"{contract_type}_case_{i:02d}", text, labels)
            cases_generated += 1

    print(f"Generated {cases_generated} test cases in {OUTPUT_DIR}")


def _write_case(name: str, text: str, labels: dict) -> None:
    (OUTPUT_DIR / f"{name}.txt").write_text(text)
    (OUTPUT_DIR / f"{name}_labels.json").write_text(
        json.dumps(labels, indent=2)
    )


if __name__ == "__main__":
    with open(CATALOG_PATH) as f:
        catalog = json.load(f)
    generate_test_cases(catalog, count=6)
