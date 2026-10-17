"""
ProofPath AI — Repository Scanning & Evidence API Router
Endpoints:
- POST /api/portfolio/{portfolio_id}/scan : Trigger bounded code scanning on selected repositories
- GET /api/portfolio/{portfolio_id}/scan/status : Retrieve real-time scan progress and telemetry
- GET /api/portfolio/{portfolio_id}/evidence : Retrieve grounded skill evidence records
"""
import logging
from typing import Any, Dict, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.supabase import get_supabase_client
from app.core.session import verify_portfolio_session
from app.schemas.scan import (
    EvidenceListResponse,
    RepositoryScanTelemetry,
    ScanInitiationRequest,
    ScanStatusResponse,
    SkillEvidenceItemSchema,
)
from app.services.repository_scanner import RepositoryScanner, ScannerError

logger = logging.getLogger("proofpath_ai.api.scans")

router = APIRouter(prefix="/api/portfolio", tags=["Scanning & Evidence"])


@router.post(
    "/{portfolio_id}/scan",
    response_model=ScanStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger bounded scanning on candidate repositories",
)
async def trigger_scan(
    portfolio_id: UUID,
    payload: Optional[ScanInitiationRequest] = None,
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> ScanStatusResponse:
    """
    Initiates bounded code scanning for candidate's selected repositories.
    Pins execution to latest commit SHA, bounds file counts and downloaded sizes,
    and extracts grounded skill evidence.
    """
    scanner = RepositoryScanner()
    requested_repo_ids = payload.repository_ids if payload else None

    try:
        telemetry = await scanner.scan_portfolio(
            portfolio_id=portfolio_id,
            repository_ids=requested_repo_ids,
        )
    except ScannerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        logger.error(f"Unexpected error running scan for portfolio {portfolio_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute code scan pipeline.",
        )

    scans_list = [
        RepositoryScanTelemetry(
            scan_id=s["scan_id"],
            repository_id=s["repository_id"],
            repository_name=s["repository_name"],
            commit_sha=s["commit_sha"],
            status=s["status"],
            files_processed=s.get("files_processed", 0),
            total_files=s.get("total_files", 0),
            skipped_summary=s.get("skipped_summary"),
            duration_ms=s.get("duration_ms"),
            started_at=s.get("started_at", ""),
            completed_at=s.get("completed_at"),
        )
        for s in telemetry.get("scans", [])
    ]

    return ScanStatusResponse(
        portfolio_id=str(portfolio_id),
        portfolio_status=telemetry.get("portfolio_status", "completed"),
        total_repositories_selected=telemetry.get("total_repositories_selected", 0),
        scans_completed=telemetry.get("scans_completed", 0),
        scans_running=telemetry.get("scans_running", 0),
        scans_failed=telemetry.get("scans_failed", 0),
        total_evidence_count=telemetry.get("total_evidence_count", 0),
        scans=scans_list,
    )


@router.get(
    "/{portfolio_id}/scan/status",
    response_model=ScanStatusResponse,
    summary="Get repository scan telemetry and status",
)
async def get_scan_status(
    portfolio_id: UUID,
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> ScanStatusResponse:
    """
    Retrieves real, persisted scan telemetry and progress for a portfolio.
    Guaranteed by verify_portfolio_session against unauthorized / cross-portfolio access.
    """
    scanner = RepositoryScanner()

    try:
        telemetry = await scanner.get_portfolio_scan_status(portfolio_id=portfolio_id)
    except ScannerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        logger.error(f"Error retrieving scan status for portfolio {portfolio_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve scan telemetry.",
        )

    scans_list = [
        RepositoryScanTelemetry(
            scan_id=s["scan_id"],
            repository_id=s["repository_id"],
            repository_name=s["repository_name"],
            commit_sha=s["commit_sha"],
            status=s["status"],
            files_processed=s.get("files_processed", 0),
            total_files=s.get("total_files", 0),
            skipped_summary=s.get("skipped_summary"),
            duration_ms=s.get("duration_ms"),
            started_at=s.get("started_at", ""),
            completed_at=s.get("completed_at"),
        )
        for s in telemetry.get("scans", [])
    ]

    return ScanStatusResponse(
        portfolio_id=str(portfolio_id),
        portfolio_status=telemetry.get("portfolio_status", "pending"),
        total_repositories_selected=telemetry.get("total_repositories_selected", 0),
        scans_completed=telemetry.get("scans_completed", 0),
        scans_running=telemetry.get("scans_running", 0),
        scans_failed=telemetry.get("scans_failed", 0),
        total_evidence_count=telemetry.get("total_evidence_count", 0),
        scans=scans_list,
    )


@router.get(
    "/{portfolio_id}/evidence",
    response_model=EvidenceListResponse,
    summary="Get extracted ground-truth skill evidence",
)
async def get_portfolio_evidence(
    portfolio_id: UUID,
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> EvidenceListResponse:
    """
    Fetches all atomic skill evidence citations extracted from scanned repositories.
    """
    p_id_str = str(portfolio_id)
    db = get_supabase_client()

    # 1. Fetch repositories belonging to this portfolio
    repos_res = (
        db.table("repositories")
        .select("id, name, full_name")
        .eq("portfolio_id", p_id_str)
        .execute()
    )
    repo_rows = repos_res.data or []
    if not repo_rows:
        return EvidenceListResponse(portfolio_id=p_id_str, total_count=0, evidence=[])

    repo_map = {r["id"]: r["full_name"] for r in repo_rows}
    repo_ids = list(repo_map.keys())

    # 2. Fetch skill evidence for these repositories
    ev_res = (
        db.table("skill_evidence")
        .select("id, scan_id, repository_id, canonical_skill, file_path, line_start, line_end, line_range, commit_sha, explanation, evidence_type, ast_node_type, snippet, limitations, created_at")
        .in_("repository_id", repo_ids)
        .order("created_at", desc=True)
        .execute()
    )
    raw_ev = ev_res.data or []

    evidence_items = [
        SkillEvidenceItemSchema(
            id=item["id"],
            scan_id=item["scan_id"],
            repository_id=item["repository_id"],
            repository_name=repo_map.get(item["repository_id"]),
            canonical_skill=item["canonical_skill"],
            file_path=item["file_path"],
            line_start=item.get("line_start"),
            line_end=item.get("line_end"),
            line_range=item.get("line_range"),
            commit_sha=item["commit_sha"],
            explanation=item["explanation"],
            evidence_type=item.get("evidence_type", "ast_node"),
            ast_node_type=item.get("ast_node_type"),
            snippet=item.get("snippet"),
            limitations=item.get("limitations"),
            created_at=item["created_at"],
        )
        for item in raw_ev
    ]

    return EvidenceListResponse(
        portfolio_id=p_id_str,
        total_count=len(evidence_items),
        evidence=evidence_items,
    )
