"""
ProofPath AI — GitHub Webhook & Activity Schemas
Defines schemas for inbound push events, signature verification, and delivery telemetry.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class GitHubCommit(BaseModel):
    """Git commit metadata inside a push event."""
    id: str = Field(..., description="Commit SHA-1 hash.")
    message: Optional[str] = Field(None, description="Commit message.")
    timestamp: Optional[str] = Field(None, description="Commit ISO-8601 timestamp.")
    added: List[str] = Field(default_factory=list, description="Files added in this commit.")
    removed: List[str] = Field(default_factory=list, description="Files removed in this commit.")
    modified: List[str] = Field(default_factory=list, description="Files modified in this commit.")


class GitHubRepository(BaseModel):
    """Repository metadata inside a push event."""
    id: Optional[int] = Field(None, description="GitHub repository numerical ID.")
    name: str = Field(..., description="Repository short name.")
    full_name: str = Field(..., description="Repository owner/name format.")
    default_branch: Optional[str] = Field("main", description="Default branch name.")
    private: Optional[bool] = Field(False, description="Whether the repository is private.")


class GitHubPushPayload(BaseModel):
    """GitHub push event payload structure."""
    ref: str = Field(..., description="Git ref that was pushed (e.g. refs/heads/main).")
    before: Optional[str] = Field(None, description="SHA before the push.")
    after: str = Field(..., description="HEAD SHA after the push.")
    repository: GitHubRepository = Field(..., description="Repository details.")
    commits: List[GitHubCommit] = Field(default_factory=list, description="List of pushed commits.")
    head_commit: Optional[GitHubCommit] = Field(None, description="Head commit metadata.")
    deleted: bool = Field(False, description="Whether this push was a branch deletion.")


class WebhookResponse(BaseModel):
    """Response returned upon processing a webhook delivery."""
    delivery_id: str
    status: Literal["queued", "processing", "completed", "duplicate", "ignored", "failed"]
    repository: Optional[str] = None
    commit_sha: Optional[str] = None
    reassessment_run_id: Optional[str] = None
    message: str


class WebhookDeliveryItem(BaseModel):
    """Persisted repository event record representing an inbound delivery."""
    id: Optional[str] = None
    delivery_id: str
    repository_name: str
    event_type: str = "push"
    commit_sha: str
    changed_paths: List[str] = Field(default_factory=list)
    received_at: str
    hmac_verified: bool = False
    status: Literal["queued", "processing", "completed", "duplicate", "failed"]
    reassessment_run_id: Optional[str] = None
    retry_count: int = 0
    error_details: Optional[str] = None
    created_at: Optional[str] = None


class ActivityResponse(BaseModel):
    """Candidate activity response returning persisted webhook deliveries."""
    portfolio_id: str
    deliveries: List[WebhookDeliveryItem]
