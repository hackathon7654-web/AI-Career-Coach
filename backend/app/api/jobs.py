"""
ProofPath AI — Target Job Ingestion & Requirements API Router
Endpoints:
- POST /api/jobs : Ingest a job posting via URL or pasted text (session authenticated)
- GET /api/jobs/{job_id} : Retrieve a saved job posting (ownership verified)
- GET /api/jobs/{job_id}/requirements : Retrieve extracted requirements (ownership verified)
- PATCH /api/jobs/{job_id}/requirements : Review, edit, add, or toggle requirements (ownership verified)
"""
import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import settings
from app.core.session import extract_session_token, get_authenticated_portfolio
from app.core.supabase import get_supabase_client
from app.schemas.job import (
    ExtractedRequirement,
    JobIngestRequest,
    JobResponse,
    RequirementsUpdateRequest,
    RequirementsUpdateResponse,
)
from app.services.job_extractor import parse_job_requirements
from app.services.job_fetcher import (
    JobFetchError,
    JobFetchSSRFError,
    fetch_job_url,
)

logger = logging.getLogger("proofpath_ai.api.jobs")

router = APIRouter(prefix="/api/jobs", tags=["Job Ingestion & Requirements"])


def compute_job_intake_sig(portfolio_id: str) -> str:
    """
    Computes a tamper-proof HMAC signature tying a newly ingested job to the authenticated portfolio.
    Prevents relying on editable free-text fields or forged parameters.
    """
    return hmac.new(
        settings.SESSION_SECRET.encode("utf-8"),
        f"job_intake:{portfolio_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def check_job_portfolio_ownership(job: Dict[str, Any], caller_portfolio: Dict[str, Any]) -> None:
    """
    Verifies that the job is legitimately associated with the authenticated portfolio.
    Uses existing relational foreign keys (assessment_runs) and cryptographic HMAC session
    intake tokens to prevent arbitrary or editable free-text spoofing.
    Fails closed if ownership cannot be securely established.
    """
    if not caller_portfolio or not caller_portfolio.get("id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: active candidate session required.",
        )

    expected_pid = str(caller_portfolio["id"])
    job_id = str(job.get("id") or "")

    # 1. Primary check: Relational foreign key in assessment_runs
    if job_id:
        try:
            client = get_supabase_client()
            res = (
                client.table("assessment_runs")
                .select("portfolio_id")
                .eq("job_id", job_id)
                .execute()
            )
            if res.data:
                associated_pids = {str(r["portfolio_id"]) for r in res.data}
                if expected_pid in associated_pids:
                    return
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: This job posting belongs to another portfolio session.",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"Error checking assessment_runs for job ownership: {exc}")

    # 2. Pre-assessment check: Cryptographically signed intake token in limitations
    limitations = job.get("limitations") or ""
    expected_sig = compute_job_intake_sig(expected_pid)
    valid_token = f"session_owner:{expected_pid}:{expected_sig}"

    if valid_token in limitations:
        return

    # Check if another portfolio session is recorded with a valid or invalid token
    if "session_owner:" in limitations:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This job belongs to another candidate session.",
        )

    # Legacy fallback: if plain portfolio_id:<uuid> was used during migration
    if f"portfolio_id:{expected_pid}" in limitations:
        return
    elif "portfolio_id:" in limitations:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This job belongs to another portfolio session.",
        )

    # Fail closed if no verified relationship exists
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: Job record is not associated with the authenticated portfolio session.",
    )


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest target job posting via URL or pasted text",
)
async def ingest_job(
    payload: JobIngestRequest,
    request: Request,
    caller_portfolio: Dict[str, Any] = Depends(get_authenticated_portfolio),
) -> JobResponse:
    """
    Accepts a job URL or pasted job description text.
    Requires authenticated candidate session.
    Defends against SSRF on URLs, cleans HTML, and deterministically extracts competencies.
    Persists job record and extracted requirements in Supabase with cryptographic ownership binding.
    """
    if not payload.job_url and not payload.pasted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either job_url or pasted_text must be provided.",
        )

    caller_pid = str(caller_portfolio["id"])
    if payload.portfolio_id and str(payload.portfolio_id) != caller_pid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Supplied portfolio ID does not match the authenticated session.",
        )

    provenance = "user_pasted"
    source_url = None
    initial_title = None
    raw_text = ""
    fetch_limitation = None

    if payload.job_url:
        provenance = "fetched"
        try:
            raw_text, initial_title, source_url = await fetch_job_url(payload.job_url)
        except JobFetchSSRFError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
        except JobFetchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message)
        except Exception as exc:
            logger.error(f"Unexpected error fetching job URL: {exc}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to fetch job description from this URL ({type(exc).__name__}). Career portals frequently block automated scraping or require JavaScript. Please switch to the 'Paste Description' tab and paste the text directly.",
            )
    else:
        raw_text = payload.pasted_text.strip()
        fetch_limitation = "Pasted by candidate directly without URL verification."

    # Parse title, company, and structured requirements
    title, company, requirements = parse_job_requirements(
        raw_text=raw_text,
        provenance=provenance,
        initial_title=initial_title,
    )

    # Encode tamper-evident cryptographic session ownership in limitations without modifying remote schema
    intake_sig = compute_job_intake_sig(caller_pid)
    limitation_parts = [
        f"session_owner:{caller_pid}:{intake_sig}",
        f"portfolio_id:{caller_pid}",
    ]
    if fetch_limitation:
        limitation_parts.append(fetch_limitation)
    limitations_str = " | ".join(limitation_parts)

    # Serialize requirements to dicts for Supabase JSONB column
    reqs_json = [r.model_dump() for r in requirements]

    client = get_supabase_client()
    try:
        insert_res = (
            client.table("jobs")
            .insert({
                "source_url": source_url,
                "provenance": provenance,
                "raw_text": raw_text[:50000],
                "title": title or "Target Job",
                "company": company,
                "requirements": reqs_json,
                "limitations": limitations_str,
                "is_archived": False,
            })
            .execute()
        )
    except Exception as exc:
        logger.error(f"Database error persisting job: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist job record in database: {str(exc)}",
        )

    if not insert_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No data returned from job insertion.",
        )

    job_row = insert_res.data[0]

    return JobResponse(
        id=str(job_row["id"]),
        source_url=job_row.get("source_url"),
        provenance=job_row.get("provenance", provenance),
        raw_text=job_row.get("raw_text"),
        title=job_row.get("title") or title or "Target Job",
        company=job_row.get("company") or company,
        requirements=requirements,
        retrieval_timestamp=str(job_row.get("retrieval_timestamp") or ""),
        limitations=job_row.get("limitations") or limitations_str,
        is_archived=bool(job_row.get("is_archived", False)),
        created_at=str(job_row.get("created_at") or ""),
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve saved job details",
)
async def get_job(
    job_id: UUID,
    caller_portfolio: Dict[str, Any] = Depends(get_authenticated_portfolio),
) -> JobResponse:
    """
    Retrieves a job description by UUID including its extracted requirements.
    Enforces candidate session authorization and ownership verification.
    """
    client = get_supabase_client()
    try:
        res = client.table("jobs").select("*").eq("id", str(job_id)).execute()
    except Exception as exc:
        logger.error(f"Error fetching job {job_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving job.")

    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")

    row = res.data[0]
    check_job_portfolio_ownership(row, caller_portfolio)

    raw_reqs = row.get("requirements") or []
    requirements = [ExtractedRequirement(**r) for r in raw_reqs]

    return JobResponse(
        id=str(row["id"]),
        source_url=row.get("source_url"),
        provenance=row.get("provenance", "user_pasted"),
        raw_text=row.get("raw_text"),
        title=row.get("title", "Target Role"),
        company=row.get("company"),
        requirements=requirements,
        retrieval_timestamp=row.get("retrieval_timestamp", ""),
        limitations=row.get("limitations"),
        is_archived=row.get("is_archived", False),
        created_at=row.get("created_at", ""),
    )


@router.get(
    "/{job_id}/requirements",
    response_model=List[ExtractedRequirement],
    summary="Retrieve extracted requirements for candidate review",
)
async def get_job_requirements(
    job_id: UUID,
    caller_portfolio: Dict[str, Any] = Depends(get_authenticated_portfolio),
) -> List[ExtractedRequirement]:
    """
    Returns the structured requirements list for candidate review.
    Enforces candidate session authorization and ownership verification.
    """
    client = get_supabase_client()
    try:
        res = client.table("jobs").select("id, limitations, requirements").eq("id", str(job_id)).execute()
    except Exception as exc:
        logger.error(f"Error fetching job requirements {job_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving requirements.")

    if not res.data:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")

    row = res.data[0]
    check_job_portfolio_ownership(row, caller_portfolio)

    raw_reqs = row.get("requirements") or []
    return [ExtractedRequirement(**r) for r in raw_reqs]


@router.patch(
    "/{job_id}/requirements",
    response_model=RequirementsUpdateResponse,
    summary="Review and modify job requirements",
)
async def update_job_requirements(
    job_id: UUID,
    payload: RequirementsUpdateRequest,
    caller_portfolio: Dict[str, Any] = Depends(get_authenticated_portfolio),
) -> RequirementsUpdateResponse:
    """
    Allows the authenticated candidate to review, edit, add, remove, or toggle requirements
    prior to running an evidence-based assessment.
    Enforces candidate session authorization and ownership verification.
    """
    client = get_supabase_client()

    # Verify job exists and check ownership
    try:
        check = client.table("jobs").select("id, limitations, is_archived").eq("id", str(job_id)).execute()
    except Exception as exc:
        logger.error(f"Error checking job {job_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error checking job existence.")

    if not check.data:
        raise HTTPException(status_code=404, detail=f"Job with ID {job_id} not found.")

    row = check.data[0]
    check_job_portfolio_ownership(row, caller_portfolio)

    if row.get("is_archived"):
        raise HTTPException(status_code=403, detail="Job posting is archived and read-only.")

    # Validate and serialize requirements
    reqs_json = [r.model_dump() for r in payload.requirements]

    try:
        update_res = (
            client.table("jobs")
            .update({"requirements": reqs_json})
            .eq("id", str(job_id))
            .execute()
        )
    except Exception as exc:
        logger.error(f"Error updating job requirements {job_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to persist updated requirements.")

    return RequirementsUpdateResponse(
        job_id=str(job_id),
        requirements_count=len(payload.requirements),
        requirements=payload.requirements,
    )

