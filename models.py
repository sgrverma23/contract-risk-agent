from __future__ import annotations
from typing import Annotated, Optional
from typing_extensions import TypedDict
from pydantic import BaseModel
from enum import Enum
from operator import add


class ContractType(str, Enum):
    NDA = "nda"
    SAAS_MSA = "saas_msa"


class RiskLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    REJECT = "reject"


class Clause(BaseModel):
    id: str
    clause_type: str
    text: str


class FlaggedClause(BaseModel):
    clause_id: str
    clause_type: str
    clause_text: str
    risk_level: RiskLevel
    reason: str
    recommendation: str
    approved: Optional[bool] = None
    reviewer_note: Optional[str] = None


class TemplateIssue(BaseModel):
    issue_type: str  # "deviation" | "missing"
    clause_type: str
    description: str
    standard_language: Optional[str] = None
    actual_language: Optional[str] = None


class TrajectoryEntry(BaseModel):
    agent: str
    input_summary: str
    output_summary: str
    tokens_used: Optional[int] = None


class ReviewState(TypedDict):
    contract_text: str
    contract_type: str
    session_id: str
    clauses: list[Clause]
    flagged_clauses: list[FlaggedClause]
    missing_clauses: list[str]
    template_issues: list[TemplateIssue]
    human_approved: list[FlaggedClause]
    final_brief: str
    trajectory: Annotated[list[TrajectoryEntry], add]
