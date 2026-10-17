"""
ProofPath AI — Repository Scan & Evidence Extraction Schemas
Defines request and response schemas for bounded code scanning, telemetry status, and skill evidence.
"""
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ScanInitiationRequest(BaseModel):
    """Optional payload to initiate bounded scanning on selected repositories."""
    repository_ids: Optional[List[UUID]] = Field(
        None,
        description="Optional subset of selected repository UUIDs to scan. If omitted, all selected repos are scanned.",
    )


class RepositoryScanTelemetry(BaseModel):
    """Telemetry item for an individual repository scan run."""
    scan_id: str
    repository_id: str
    repository_name: str
    commit_sha: str
    status: str = Field(..., description="Status: queued | running | completed | partial | failed")
    files_processed: int = 0
    total_files: int = 0
    skipped_summary: Optional[str] = None
    duration_ms: Optional[int] = None
    started_at: str
    completed_at: Optional[str] = None


class SkillEvidenceItemSchema(BaseModel):
    """Detailed ground-truth code evidence item."""
    id: str
    scan_id: str
    repository_id: str
    repository_name: Optional[str] = None
    canonical_skill: str
    file_path: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    line_range: Optional[str] = None
    commit_sha: str
    explanation: str
    evidence_type: str = Field("ast_node", description="ast_node | file_match | manifest | workflow")
    ast_node_type: Optional[str] = None
    snippet: Optional[str] = None
    limitations: Optional[str] = None
    created_at: str


class ScanStatusResponse(BaseModel):
    """Consolidated telemetry and status response for a portfolio's scanning pipeline."""
    portfolio_id: str
    portfolio_status: str
    total_repositories_selected: int
    scans_completed: int
    scans_running: int
    scans_failed: int
    total_evidence_count: int
    scans: List[RepositoryScanTelemetry]


class EvidenceListResponse(BaseModel):
    """Response containing extracted evidence items for a portfolio."""
    portfolio_id: str
    total_count: int
    evidence: List[SkillEvidenceItemSchema]
