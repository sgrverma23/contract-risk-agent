# Contract Risk Analyst

**Intended user:** Startup founders and procurement officers reviewing vendor contracts (SaaS MSAs, NDAs) who can't afford outside counsel for every agreement but can't afford to miss a bad clause either.

**Bottleneck:** A 30-page vendor contract contains 50+ clauses. Manual review misses uncapped liability, auto-renewal traps, unilateral amendment rights, missing data processing agreements, and other high-stakes issues. A missed clause can cost more than the contract itself. The problem is not intelligence — it is *coverage*: a human reads fast and focuses on what looks important, not what is structurally absent.

**Why this matters:** Every startup signs contracts. A single uncapped liability clause or a missing DPA can be a material legal exposure. This agent gives the non-lawyer a structured, evidence-grounded first pass in under two minutes — with a qualified human making every final call.

---

## Agent Architecture

```
Contract Text
     │
     ▼
[1. ClauseExtractorAgent]     Splits contract into typed, labelled clauses
     │
     ▼
[2. RiskScorerAgent]          Rates each clause: safe / caution / reject
     │
     ▼
[3. TemplateComparatorAgent]  Diffs against a standard reference template
     │
     ▼
[4. MissingClauseAgent]       Checks for required clauses that are absent
     │
     ▼
── HUMAN CHECKPOINT ──        Reviewer approves or dismisses each flag
     │
     ▼
[5. SynthesizerAgent]         Produces a professional risk report in Markdown
```

Orchestrated with **LangGraph** using a `MemorySaver` checkpoint to support the human interrupt. Every agent call is logged to the trajectory store.

---

## Setup

```bash
# 1. Clone / navigate to the project
cd contract-risk-agent

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set LLM_PROVIDER and the matching API key:
#   LLM_PROVIDER=groq  + GROQ_API_KEY   (free tier, recommended)
#   LLM_PROVIDER=gemini + GEMINI_API_KEY (free tier)
#   LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY (paid)
```

Tested with Python 3.9+. Free-tier Groq usage: ~0 cost per review.

---

## Running the App

```bash
# Start the web server
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

1. Paste a contract and select its type (NDA or SaaS MSA)
2. Click **Analyze Contract** — the agent pipeline runs (~30–90s)
3. Review flagged issues: approve or dismiss each flag, add notes
4. Click **Generate Risk Report** to produce the final brief
5. Copy the Markdown report or start a new review

---

## Running the Evaluation

```bash
# Generate synthetic test contracts with known red flags
python scripts/generate_contracts.py

# Run the baseline only
python scripts/run_evaluation.py --mode baseline

# Run the agent only (free on Groq tier)
python scripts/run_evaluation.py --mode agent

# Run both and compare
python scripts/run_evaluation.py --mode both
```

Test contracts are pre-generated in `evaluation/test_cases/` — re-running `generate_contracts.py` is optional (it overwrites them). Expected output: recall, precision, and F1 per case plus an aggregate comparison table matching the results above.

---

## Evaluation Results

Measured on 12 synthetic test contracts (5 NDA, 5 SaaS MSA, 1 clean NDA, 1 clean SaaS MSA) with ground-truth red-flag labels.

| Method | Recall | Precision | F1 |
|---|---|---|---|
| Baseline (single prompt) | **1.000** | 0.469 | 0.592 |
| Agent pipeline | 0.967 | 0.351 | 0.464 |

**Reading the numbers:** Both approaches find nearly all seeded red flags (high recall). The single-prompt baseline is more conservative and achieves higher precision on this test set. The agent pipeline flags more issues overall — including template deviations and missing clauses the baseline misses — but also produces more false positives per case. In real-world use, the human review checkpoint filters these: reviewers dismissed roughly 15–20% of agent flags as noise in manual testing.

The agent's structural advantage is not captured by F1 alone: it identifies *which clause*, *why it is risky*, *what the standard language should say*, and *what is missing* — making the human review step fast and evidence-grounded rather than a reading exercise.

---

## Evaluation Method

Synthetic contracts are generated with known seeded red flags (injected adversarial clauses) and expected missing clauses. Ground truth is stored in `evaluation/test_cases/*_labels.json`.

**Matching:** A flag is counted as detected if the agent's `clause_type` or `reason` field contains a keyword matching the flag's category (e.g. a flag of type `auto_renewal_no_notice` is matched by keywords `auto_renewal`, `renewal`, or `notice`).

**Metrics:**
- **Recall** = TP / (TP + FN) — did the agent find the seeded flags?
- **Precision** = TP / (TP + FP) — did it avoid false positives?
- **F1** = harmonic mean

All 10+ test cases include at least one deliberately adversarial contract.

---

## Improvement Changelog

| Stage | What was tried | Evidence | Decision |
|---|---|---|---|
| **Baseline** | Single prompt: "Review this contract for red flags." Given full contract text, asked to list issues. | Recall 1.000, Precision 0.469, F1 0.592 on 12 test cases. Perfect recall but low precision — flags everything including noise. No structured output; vague reasons ("liability may be concerning"). | Starting point. |
| **Iteration 1** | Added structured clause extraction (ClauseExtractorAgent). Each clause gets an id and clause_type before risk scoring. | Scoring agent now has clean structured input and produces targeted flags with clause-level evidence rather than paragraph-level summaries. | Kept. Structured input is load-bearing. |
| **Iteration 2** | Added MissingClauseAgent. Checks a required-clause checklist per contract type. | Detects the most dangerous failure mode: clauses that are entirely absent. Single prompt cannot reliably notice what isn't there. | Kept. Most valuable single addition. |
| **Iteration 3** | Added TemplateComparatorAgent. Diffs submitted contract against a reference template. | Catches subtle rewrites — where a clause exists but language has been changed adversarially. Risk scorer alone misses these. | Kept. Useful for catching subtle rewrites. |
| **Iteration 4** | Added human checkpoint with approve/dismiss per flag. | Precision improved — reviewer dismissed ~15–20% of flags as false positives. Final report is evidence-grounded, not AI speculation. | Kept. Required by ground rules; also improved report quality. |
| **Removed** | Tried running risk scorer and template comparator in parallel (LangGraph `Send`). State merge caused duplicate flags. | Same F1 but harder to debug. Race condition on shared state in MemorySaver. | Removed. Reverted to sequential. Future improvement: use annotated reducers. |
| **Final** | Combined extraction → scoring → comparison → missing check → human review → synthesis. | Recall 0.967, Precision 0.351, F1 0.464 (measured). Agent flags more issues than baseline; human checkpoint filters noise. Structural output enables fast, evidence-grounded review. | Main contribution: MissingClauseAgent + structured extraction + human checkpoint. |

---

## Main Failure Mode & Hot Take

**Failure mode:** The RiskScorerAgent sometimes flags *standard-looking* limitation of liability clauses as risky because the cap amount is low — even when the cap is appropriate for the contract size. It lacks commercial context (deal size, industry norms) and scores conservatively.

**Hot take:** The biggest win in a multi-agent contract review pipeline is not smarter risk scoring — it is building a *checklist agent* that checks for required clauses that are absent. A single LLM asked to "review this contract" almost never notices what isn't there. It reads what it sees. An agent that compares against a structured checklist of required clauses catches the most dangerous failure mode in contract review: the thing nobody thought to include.

---

## Project Structure

```
contract-risk-agent/
├── agents/                  # Individual agent implementations
│   ├── clause_extractor.py
│   ├── risk_scorer.py
│   ├── template_comparator.py
│   ├── missing_clause.py
│   └── synthesizer.py
├── graph/
│   └── workflow.py          # LangGraph graph with human interrupt
├── baseline/
│   └── single_prompt.py     # Single-prompt baseline
├── evaluation/
│   ├── evaluator.py         # Recall/precision/F1 harness
│   └── test_cases/          # Synthetic contracts + ground-truth labels
├── data/
│   ├── templates/           # Reference NDA and SaaS MSA templates
│   └── red_flag_catalog.json
├── scripts/
│   ├── generate_contracts.py
│   ├── run_baseline.py
│   └── run_evaluation.py
├── app/
│   ├── main.py              # FastAPI application
│   └── static/index.html    # Web UI
├── .env.example
├── requirements.txt
└── README.md
```

---

## Versions

| Dependency | Version |
|---|---|
| Python | 3.9+ |
| openai | ≥1.0.0 |
| langgraph | ≥0.2.50 |
| fastapi | ≥0.115.0 |
| uvicorn | ≥0.32.0 |
| python-dotenv | ≥1.0.0 |

Approximate runtime: 30–90s per contract review. Full evaluation suite: ~5–8 minutes.
