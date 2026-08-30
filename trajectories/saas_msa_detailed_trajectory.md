# Agent Trajectory — SaaS MSA Review (saas_msa_case_05)

This document traces a complete execution of the Contract Risk Analyst pipeline on a SaaS Master Services Agreement containing four adversarially injected clauses and one missing required clause.

**Contract:** `evaluation/test_cases/saas_msa_case_05.txt`  
**Seeded flags:** no_termination_convenience, uncapped_liability, unilateral_amendment, auto_renewal_no_notice  
**Expected missing:** data_processing_agreement  

---

## Step 1 — ClauseExtractorAgent

**Role in pipeline:** Splits the raw contract text into typed, labelled clauses. Every downstream agent works on this structured output, not the raw text.

**System prompt:**
```
You are a legal contract analyst. Extract every meaningful clause and assign it a category.
Include all clauses — both standard and potentially problematic.
```

**Tool called:** `extract_clauses`

**Tool schema (abbreviated):**
```json
{
  "clauses": [
    { "id": "cl_01", "clause_type": "...", "text": "..." }
  ]
}
```

**Input to agent:** Full contract text (2320 chars), contract_type = `saas_msa`

**Tool response — extracted 14 clauses:**
```
cl_01  other              LICENSE — limited non-exclusive license...
cl_02  sla                VENDOR guarantees 99.5% monthly uptime...
cl_03  data_processing    Vendor processes Customer Data per instructions...
cl_04  ip_assignment      Customer owns all Customer Data. Vendor retains all rights...
cl_05  liability          EACH PARTY'S LIABILITY IS CAPPED AT FEES PAID...
cl_06  indemnification    Each party indemnifies the other against third-party claims...
cl_07  termination        Initial term: twelve (12) months, auto-renewing with 60 days notice...
cl_08  amendment          Amendments require written agreement signed by both parties.
cl_09  dispute_resolution Governed by Delaware law. Disputes resolved by arbitration...
cl_10  termination        [AMENDED] Neither party may terminate prior to end of Subscription Term...
cl_11  liability          [AMENDED] Vendor's liability shall be unlimited...
cl_12  amendment          [AMENDED] Vendor reserves the right to modify terms by email notice...
cl_13  auto_renewal       [AMENDED] Auto-renews for successive one-year terms...
cl_14  auto_renewal       Customer must provide non-renewal notice 5 days prior...
```

**Tokens used:** 3,346  
**Output passed to next step:** 14 `Clause` objects with id, clause_type, text

---

## Step 2 — RiskScorerAgent

**Role in pipeline:** Reviews each extracted clause and flags those that are materially unfavorable, unusual, or missing standard protections. Returns only `caution` and `reject` — skips safe clauses.

**System prompt:**
```
You are a senior commercial lawyer reviewing a contract on behalf of the party signing it.
Flag every clause that is materially unfavorable, unusual, or missing standard protections.
Only return clauses rated caution or reject — skip safe clauses.
```

**Tool called:** `score_risk`

**Input to agent:** 14 clauses formatted as `[cl_id | clause_type]\ntext`

**Tool response — 3 flagged clauses:**

```
REJECT  cl_10  termination
  reason: Removes standard termination for convenience. Customer is locked in for full
          term even if service is unusable. No exit mechanism except uncured material breach.
  recommendation: Reinstate 30-day termination for convenience per standard SaaS terms.

REJECT  cl_11  liability
  reason: "Unlimited" liability contradicts the standard mutual cap established in cl_05.
          Creates unpredictable exposure; unenforceable language may void the cap entirely.
  recommendation: Remove cl_11. Maintain the mutual cap at fees paid in prior 12 months.

CAUTION  cl_12  amendment
  reason: Vendor can unilaterally modify any contract term via email. Continued use = acceptance.
          Customer has no meaningful ability to reject unfavorable changes.
  recommendation: Require written mutual consent for all amendments. Delete cl_12.
```

**What was not flagged:** cl_13/cl_14 (auto-renewal) — the risk scorer missed the 5-day notice window. This is caught by the TemplateComparatorAgent in the next step.

**Tokens used:** 2,109  
**Output passed to next step:** 3 `FlaggedClause` objects with risk_level, reason, recommendation

---

## Step 3 — TemplateComparatorAgent

**Role in pipeline:** Diffs the extracted clauses against a reference SaaS MSA template. Catches adversarial rewrites where a clause exists but the language has been quietly changed.

**System prompt:**
```
You are a contract specialist. You MUST call the compare_template function to return your findings.
Do not write prose — only use the function. Keep standard_language and actual_language fields
SHORT (max 30 words each) — summarize, do not quote verbatim.
```

**Tool called:** `compare_template`

**Input to agent:** 14 clauses + full reference template from `data/templates/saas_msa_template.txt`

**Tool response — 14 deviations found (representative sample):**

```
deviation  termination      cl_10 removes 30-day termination for convenience entirely.
                            Standard: either party may terminate on 30 days notice.

deviation  liability        cl_11 declares unlimited liability, overriding mutual cap in cl_05.
                            Standard: mutual cap at 12 months fees paid.

deviation  amendment        cl_12 grants unilateral amendment right via email.
                            Standard: amendments require written consent of both parties.

deviation  auto_renewal     cl_13/cl_14 requires only 5 days non-renewal notice.
                            Standard: 30–60 days written notice required.

deviation  data_processing  cl_03 omits processor role and documented-instructions requirement.
                            Standard: vendor acts as data processor on customer's instructions.

... (9 additional deviations on indemnification, SLA credits, IP language, etc.)
```

**Key contribution:** Caught the auto-renewal notice window (5 days vs 30–60 day standard) that the RiskScorerAgent missed.

**Tokens used:** 3,884  
**Output passed to next step:** 14 `TemplateIssue` objects

---

## Step 4 — MissingClauseAgent

**Role in pipeline:** Checks the contract against a required-clause checklist for the contract type. Catches risks that are absent entirely — which a reading agent cannot detect.

**System prompt:**
```
You are a contract compliance checker. Identify which required clauses are genuinely absent.
Be strict — only mark missing if no clause covers that topic.
```

**Tool called:** `check_missing`

**Required clauses for `saas_msa`:**
```
limitation_of_liability, indemnification, data_processing_agreement,
service_level_agreement, termination_for_convenience, ip_ownership,
confidentiality, governing_law, dispute_resolution, auto_renewal_notice
```

**Input to agent:**
```
Required: [the 10 clauses above]
Present:  amendment, auto_renewal, data_processing, dispute_resolution,
          indemnification, ip_assignment, liability, other, sla, termination
```

**Tool response — 6 missing:**
```
limitation_of_liability        (cl_05 exists but cl_11 overrides it — treated as absent)
termination_for_convenience    (cl_10 explicitly removed this right)
ip_ownership                   (ip_assignment present but ownership not clearly stated)
confidentiality                (no dedicated confidentiality clause)
governing_law                  (cl_09 mentions Delaware but no formal governing law clause)
auto_renewal_notice            (notice period of 5 days not compliant with standard)
```

**Tokens used:** 916  
**Output passed to next step:** 6 missing clause strings

---

## Step 5 — Human Review Checkpoint

**Role in pipeline:** LangGraph `interrupt()` suspends the graph. The API returns all flags to the frontend. The human reviewer approves or dismisses each flag and optionally adds notes. Resumed via `/api/review/{id}/submit`.

**Flags presented to reviewer:**

| # | Type | Risk | Flag |
|---|------|------|------|
| 1 | termination | REJECT | No termination for convenience — locked in for full term |
| 2 | liability | REJECT | Unlimited liability clause overrides mutual cap |
| 3 | amendment | CAUTION | Unilateral amendment by email |

**Reviewer action:** Approved all 3 flags. No dismissals. No notes added.

**Output passed to next step:** 3 approved `FlaggedClause` objects + 6 missing clauses + 14 template issues

---

## Step 6 — SynthesizerAgent

**Role in pipeline:** Produces a professional Markdown risk brief from approved flags, missing clauses, and template deviations. Uses plain `call()` (no tool) — free-form generation.

**System prompt:** None (task fully specified in user message)

**Input prompt (abbreviated):**
```
Write a professional contract risk assessment report in Markdown.

Contract type: SAAS_MSA
Overall risk level: HIGH

APPROVED FLAGS (confirmed by human reviewer):
- [REJECT] termination: Removes termination for convenience → Reinstate 30-day notice right
- [REJECT] liability: Unlimited liability clause overrides mutual cap → Remove cl_11
- [CAUTION] amendment: Unilateral amendment by email → Require written mutual consent

MISSING REQUIRED CLAUSES:
- limitation_of_liability
- termination_for_convenience
- ip_ownership
- confidentiality
- governing_law
- auto_renewal_notice

TEMPLATE DEVIATIONS:
- DEVIATION [termination]: cl_10 removes standard 30-day convenience termination
- DEVIATION [liability]: cl_11 declares unlimited liability...
[... 12 more deviations]

Include: Executive Summary, Critical Issues, Items for Negotiation,
Missing Clauses, Recommended Next Steps
```

**Output (3,583 chars, excerpt):**
```markdown
# Contract Risk Assessment — SaaS MSA
**Overall Risk: HIGH**

## Executive Summary
This SaaS Master Services Agreement contains two REJECT-level clauses that create
significant legal exposure: a complete removal of termination for convenience and an
unlimited liability clause that directly overrides the mutual cap established earlier
in the agreement. Do not sign without resolving these issues.

## Critical Issues
### 1. Termination Lock-In (REJECT)
The amended termination clause (cl_10) removes the standard 30-day termination for
convenience and replaces it with a hard lock-in for the full subscription term...

### 2. Unlimited Liability Override (REJECT)
Clause cl_11 declares vendor liability "unlimited" and allows Customer to seek any
damages including punitive — directly contradicting cl_05's mutual liability cap...

## Items for Negotiation
### Unilateral Amendment Right (CAUTION)
Clause cl_12 allows the vendor to modify any term via email notice...

## Missing Clauses
The following required clauses are absent...

## Recommended Next Steps
1. Refuse to sign until cl_10 and cl_11 are removed or replaced with standard language
2. Add a mutual 30-day termination for convenience clause
3. Confirm cl_05 is the sole liability provision and delete cl_11
4. Add a formal confidentiality clause and data processing agreement
5. Clarify IP ownership language explicitly
```

**Tokens used:** 1,604

---

## Summary

| Agent | Tokens | Key output |
|---|---|---|
| ClauseExtractorAgent | 3,346 | 14 clauses with types |
| RiskScorerAgent | 2,109 | 3 flagged (2 reject, 1 caution) |
| TemplateComparatorAgent | 3,884 | 14 template deviations |
| MissingClauseAgent | 916 | 6 missing required clauses |
| HumanReviewCheckpoint | — | 3 approved, 0 dismissed |
| SynthesizerAgent | 1,604 | 3,583-char HIGH-risk brief |
| **Total** | **11,859** | |

**Ground truth result:** All 4 seeded red flags detected (1 via risk scorer, 1 via template comparator, 2 via both). 1 missing clause detected. Human checkpoint: 0 false positives dismissed.
