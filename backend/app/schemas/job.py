"""
ProofPath AI — Job Ingestion & Requirements Schemas
Defines request and response schemas for job posting ingestion, URL fetch, and candidate requirements review.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, field_validator


class JobIngestRequest(BaseModel):
    """Payload to ingest a target job description via URL or pasted text."""
    job_url: Optional[str] = Field(
        None,
        description="Public HTTPS/HTTP URL of the job posting.",
        max_length=2048,
    )
    pasted_text: Optional[str] = Field(
        None,
        description="Raw job description text pasted by the candidate.",
        max_length=50000,
    )
    portfolio_id: Optional[UUID] = Field(
        None,
        description="Optional portfolio ID to bind job ownership to the candidate intake session.",
    )

    @field_validator("job_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip()
        if not clean:
            return None
        # Reject credentials in URL e.g. http://user:pass@host
        if "@" in clean.split("/")[2] if len(clean.split("/")) > 2 else False:
            raise ValueError("Credentials embedded in job URLs are strictly prohibited.")
        if not (clean.startswith("http://") or clean.startswith("https://")):
            raise ValueError("Only http:// and https:// URLs are supported.")
        return clean

    @field_validator("pasted_text")
    @classmethod
    def validate_content(cls, v: Optional[str], values) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if len(clean.encode("utf-8")) > 50000:
                raise ValueError("Job text exceeds maximum retention limit of 50,000 bytes.")
            return clean
        return v


class ExtractedRequirement(BaseModel):
    """Individual job requirement extracted from the posting."""
    id: str = Field(..., description="Unique requirement ID (e.g. req_01, custom_123).")
    skill_name: str = Field(..., min_length=1, max_length=200, description="Skill or competency name.")
    category: Literal["core_required", "preferred_differentiator"] = Field(
        "core_required",
        description="Requirement priority category."
    )
    description: Optional[str] = Field(None, max_length=2000, description="Contextual snippet or description.")
    provenance: str = Field("user_pasted", description="Origin: fetched | user_pasted | candidate_added")
    tags: List[str] = Field(default_factory=list, description="Associated skills, languages, or framework tags.")
    section_label: Optional[str] = Field(None, description="Section heading from which requirement was extracted.")
    is_included: bool = Field(True, description="Whether included in the evaluation scope.")
    is_candidate_edited: bool = Field(False, description="Whether modified or added by the candidate.")


class JobResponse(BaseModel):
    """Response returned upon creating or fetching a job record."""
    id: str
    source_url: Optional[str] = None
    provenance: Literal["fetched", "user_pasted"]
    raw_text: Optional[str] = None
    title: str
    company: Optional[str] = None
    requirements: List[ExtractedRequirement] = Field(default_factory=list)
    retrieval_timestamp: str
    limitations: Optional[str] = None
    is_archived: bool = False
    created_at: str


class RequirementsUpdateRequest(BaseModel):
    """Payload to review and update requirements for a job."""
    requirements: List[ExtractedRequirement] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Updated list of candidate-reviewed requirements.",
    )


class RequirementsUpdateResponse(BaseModel):
    """Response returned after candidate review and modification of requirements."""
    job_id: str
    requirements_count: int
    requirements: List[ExtractedRequirement]
    message: str = "Job requirements updated successfully."
