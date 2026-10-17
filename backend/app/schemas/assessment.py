"""
ProofPath AI — Assessment & Comparison Schemas
Defines request and response schemas for evidence-based assessment runs, history snapshots, and comparisons.
"""
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


AssessmentStatusType = Literal[
    "demonstrated",
    "partially_demonstrated",
    "not_demonstrated_in_scope",
    "uncertain",
]


class AssessmentEvidenceReference(BaseModel):
    """Citation link to ground-truth code evidence."""
    id: str
    repository_id: str
    repository_name: Optional[str] = None
    canonical_skill: str
    file_path: str
    line_range: Optional[str] = None
    commit_sha: str
    explanation: str
    evidence_type: str
    snippet: Optional[str] = None


class AssessmentResultItem(BaseModel):
    """Evaluation result for an individual job requirement."""
    id: Optional[str] = None
    requirement_id: str
    skill_name: str
    category: Literal["core_required", "preferred_differentiator"] = "core_required"
    status: AssessmentStatusType
    explanation: str
    evidence_ids: List[str] = Field(default_factory=list)
    evidence_items: List[AssessmentEvidenceReference] = Field(default_factory=list)
    limitations: Optional[str] = None
    suggestion: Optional[str] = None


class AssessmentStatusSummary(BaseModel):
    """Status counts and telemetry for an assessment snapshot."""
    demonstrated_count: int = 0
    partially_demonstrated_count: int = 0
    not_demonstrated_in_scope_count: int = 0
    uncertain_count: int = 0
    total_requirements: int = 0
    scanned_repositories_count: int = 0
    total_evidence_count: int = 0


class AssessmentRunResponse(BaseModel):
    """Immutable assessment run snapshot with child requirement results."""
    id: str
    portfolio_id: str
    job_id: str
    job_title: Optional[str] = None
    job_company: Optional[str] = None
    snapshot_number: int
    trigger_type: Literal["initial_scan", "webhook_push", "manual_rescan"]
    commit_references: Dict[str, str] = Field(default_factory=dict)
    status_summary: AssessmentStatusSummary
    results: List[AssessmentResultItem] = Field(default_factory=list)
    created_at: str


class AssessmentRunListItem(BaseModel):
    """Summary item for chronological history ledger."""
    id: str
    portfolio_id: str
    job_id: str
    job_title: Optional[str] = None
    snapshot_number: int
    trigger_type: str
    commit_references: Dict[str, str] = Field(default_factory=dict)
    status_summary: AssessmentStatusSummary
    created_at: str


class AssessmentHistoryResponse(BaseModel):
    """Chronological ledger of assessment snapshots."""
    portfolio_id: str
    total_runs: int
    runs: List[AssessmentRunListItem]


class RequirementStatusTransition(BaseModel):
    """Delta transition between two snapshots for a requirement."""
    requirement_id: str
    skill_name: str
    category: str
    base_status: Optional[str] = None
    target_status: str
    status_changed: bool
    evidence_delta_count: int = 0
    explanation: str


class AssessmentComparisonResponse(BaseModel):
    """Comparison matrix between base and target assessment snapshots."""
    portfolio_id: str
    base_run_id: str
    base_snapshot_number: int
    base_created_at: str
    target_run_id: str
    target_snapshot_number: int
    target_created_at: str
    job_id: str
    job_title: Optional[str] = None
    transitions: List[RequirementStatusTransition] = Field(default_factory=list)
    summary_delta: Dict[str, int] = Field(default_factory=dict)
    limitations: Optional[str] = None
