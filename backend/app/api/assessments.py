"""
ProofPath AI — Evidence-Based Assessment, History & Comparison API Router
Endpoints:
- POST /api/portfolio/{portfolio_id}/assess/{job_id} : Run evidence assessment and create immutable snapshot
- GET /api/portfolio/{portfolio_id}/assessments : List chronological assessment run history
- GET /api/portfolio/{portfolio_id}/assessments/compare : Compare two snapshots and return delta matrix
- GET /api/portfolio/{portfolio_id}/assessments/{run_id} : Retrieve a specific assessment snapshot
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.session import verify_portfolio_session
from app.core.supabase import get_supabase_client
from app.schemas.assessment import (
    AssessmentComparisonResponse,
    AssessmentEvidenceReference,
    AssessmentHistoryResponse,
    AssessmentResultItem,
    AssessmentRunListItem,
    AssessmentRunResponse,
    AssessmentStatusSummary,
    RequirementStatusTransition,
)
from app.services.assessment_engine import (
    AssessmentEngineError,
    get_assessment_service,
)

logger = logging.getLogger("proofpath_ai.api.assessments")

router = APIRouter(prefix="/api/portfolio", tags=["Assessment, History & Comparison"])


@router.post(
    "/{portfolio_id}/assess/{job_id}",
    response_model=AssessmentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute evidence-based assessment against target job",
)
async def create_assessment(
    portfolio_id: UUID,
    job_id: UUID,
    trigger_type: str = Query("initial_scan", description="Trigger: initial_scan | manual_rescan"),
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> AssessmentRunResponse:
    """
    Evaluates candidate's ground-truth code evidence against the target job requirements.
    Creates an immutable assessment run snapshot and per-requirement result records.
    """
    service = get_assessment_service()
    try:
        run = await service.run_assessment(
            portfolio_id=portfolio_id,
            job_id=job_id,
            trigger_type=trigger_type,
        )
        return run
    except AssessmentEngineError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        logger.error(f"Unexpected error executing assessment: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete evidence assessment.",
        )


@router.get(
    "/{portfolio_id}/assessments",
    response_model=AssessmentHistoryResponse,
    summary="List chronological assessment run snapshots",
)
async def list_assessments(
    portfolio_id: UUID,
    job_id: Optional[UUID] = Query(None, description="Optional job ID filter"),
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> AssessmentHistoryResponse:
    """
    Retrieves chronological history of assessment snapshots for the portfolio.
    """
    client = get_supabase_client()
    p_id_str = str(portfolio_id)

    try:
        query = (
            client.table("assessment_runs")
            .select("id, portfolio_id, job_id, snapshot_number, trigger_type, commit_references, status_summary, created_at, jobs(title)")
            .eq("portfolio_id", p_id_str)
            .order("snapshot_number", desc=True)
        )
        if job_id:
            query = query.eq("job_id", str(job_id))
        
        res = query.execute()
    except Exception as exc:
        logger.error(f"Error fetching assessment history for portfolio {portfolio_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving assessment history.")

    items: List[AssessmentRunListItem] = []
    for row in res.data or []:
        raw_summary = row.get("status_summary") or {}
        summary = AssessmentStatusSummary(**raw_summary) if isinstance(raw_summary, dict) else AssessmentStatusSummary()
        
        job_info = row.get("jobs") or {}
        job_title = job_info.get("title") if isinstance(job_info, dict) else None

        items.append(
            AssessmentRunListItem(
                id=str(row["id"]),
                portfolio_id=str(row["portfolio_id"]),
                job_id=str(row["job_id"]),
                job_title=job_title,
                snapshot_number=row.get("snapshot_number", 1),
                trigger_type=row.get("trigger_type", "initial_scan"),
                commit_references=row.get("commit_references") or {},
                status_summary=summary,
                created_at=row.get("created_at", ""),
            )
        )

    return AssessmentHistoryResponse(
        portfolio_id=p_id_str,
        total_runs=len(items),
        runs=items,
    )


@router.get(
    "/{portfolio_id}/assessments/compare",
    response_model=AssessmentComparisonResponse,
    summary="Compare two assessment snapshots and return delta matrix",
)
async def compare_assessments(
    portfolio_id: UUID,
    base_run_id: UUID = Query(..., description="Base (earlier) snapshot ID"),
    target_run_id: UUID = Query(..., description="Target (later) snapshot ID"),
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> AssessmentComparisonResponse:
    """
    Compares two assessment snapshots belonging to the portfolio.
    Computes status transitions, evidence additions, and score changes.
    Rejects cross-portfolio requests or incompatible snapshot pairs.
    """
    client = get_supabase_client()
    p_id_str = str(portfolio_id)
    base_id_str = str(base_run_id)
    target_id_str = str(target_run_id)

    # Fetch both runs
    try:
        runs_res = (
            client.table("assessment_runs")
            .select("id, portfolio_id, job_id, snapshot_number, status_summary, created_at, jobs(title)")
            .in_("id", [base_id_str, target_id_str])
            .execute()
        )
    except Exception as exc:
        logger.error(f"Error fetching comparison runs: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving comparison runs.")

    runs_by_id = {r["id"]: r for r in (runs_res.data or [])}

    if base_id_str not in runs_by_id or target_id_str not in runs_by_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both of the specified assessment run IDs do not exist.",
        )

    base_run = runs_by_id[base_id_str]
    target_run = runs_by_id[target_id_str]

    # Verify both belong to authenticated portfolio
    if base_run["portfolio_id"] != p_id_str or target_run["portfolio_id"] != p_id_str:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot compare snapshots outside your authenticated portfolio session.",
        )

    # Verify both evaluate the same job
    if base_run["job_id"] != target_run["job_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Snapshots target different job descriptions and cannot be directly compared.",
        )

    # Fetch child assessment_results for both runs
    try:
        results_res = (
            client.table("assessment_results")
            .select("*")
            .in_("assessment_run_id", [base_id_str, target_id_str])
            .execute()
        )
    except Exception as exc:
        logger.error(f"Error fetching results for comparison: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving snapshot results.")

    base_results = {r["requirement_id"]: r for r in (results_res.data or []) if r["assessment_run_id"] == base_id_str}
    target_results = {r["requirement_id"]: r for r in (results_res.data or []) if r["assessment_run_id"] == target_id_str}

    transitions: List[RequirementStatusTransition] = []
    all_req_ids = set(base_results.keys()).union(set(target_results.keys()))

    for r_id in all_req_ids:
        b_res = base_results.get(r_id)
        t_res = target_results.get(r_id)

        skill_name = t_res["skill_name"] if t_res else (b_res["skill_name"] if b_res else r_id)
        category = t_res["category"] if t_res else (b_res["category"] if b_res else "core_required")
        base_status = b_res["status"] if b_res else None
        target_status = t_res["status"] if t_res else "not_demonstrated_in_scope"
        changed = base_status != target_status

        base_ev_count = len(b_res.get("evidence_ids") or []) if b_res else 0
        target_ev_count = len(t_res.get("evidence_ids") or []) if t_res else 0
        ev_delta = target_ev_count - base_ev_count

        if changed:
            explanation = f"Transitioned from {base_status or 'unassessed'} to {target_status} ({ev_delta:+d} citations)."
        else:
            explanation = f"Status unchanged: {target_status}."

        transitions.append(
            RequirementStatusTransition(
                requirement_id=r_id,
                skill_name=skill_name,
                category=category,
                base_status=base_status,
                target_status=target_status,
                status_changed=changed,
                evidence_delta_count=ev_delta,
                explanation=explanation,
            )
        )

    # Compute summary delta
    base_summary = base_run.get("status_summary") or {}
    target_summary = target_run.get("status_summary") or {}

    summary_delta = {
        "demonstrated_delta": target_summary.get("demonstrated_count", 0) - base_summary.get("demonstrated_count", 0),
        "partially_demonstrated_delta": target_summary.get("partially_demonstrated_count", 0) - base_summary.get("partially_demonstrated_count", 0),
        "not_demonstrated_in_scope_delta": target_summary.get("not_demonstrated_in_scope_count", 0) - base_summary.get("not_demonstrated_in_scope_count", 0),
        "uncertain_delta": target_summary.get("uncertain_count", 0) - base_summary.get("uncertain_count", 0),
        "evidence_delta": target_summary.get("total_evidence_count", 0) - base_summary.get("total_evidence_count", 0),
    }

    job_title = None
    if isinstance(target_run.get("jobs"), dict):
        job_title = target_run["jobs"].get("title")

    return AssessmentComparisonResponse(
        portfolio_id=p_id_str,
        base_run_id=base_id_str,
        base_snapshot_number=base_run.get("snapshot_number", 1),
        base_created_at=base_run.get("created_at", ""),
        target_run_id=target_id_str,
        target_snapshot_number=target_run.get("snapshot_number", 2),
        target_created_at=target_run.get("created_at", ""),
        job_id=str(target_run["job_id"]),
        job_title=job_title,
        transitions=transitions,
        summary_delta=summary_delta,
        limitations=None,
    )


@router.get(
    "/{portfolio_id}/assessments/{run_id}",
    response_model=AssessmentRunResponse,
    summary="Retrieve a specific assessment run snapshot with code citations",
)
async def get_assessment(
    portfolio_id: UUID,
    run_id: UUID,
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> AssessmentRunResponse:
    """
    Retrieves a historical assessment run with all child requirement results and ground-truth code citations.
    """
    client = get_supabase_client()
    p_id_str = str(portfolio_id)
    r_id_str = str(run_id)

    try:
        run_res = (
            client.table("assessment_runs")
            .select("*, jobs(title, company)")
            .eq("id", r_id_str)
            .eq("portfolio_id", p_id_str)
            .execute()
        )
    except Exception as exc:
        logger.error(f"Error fetching assessment run {run_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving assessment run.")

    if not run_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment run {run_id} not found for this portfolio.",
        )

    run_row = run_res.data[0]
    job_info = run_row.get("jobs") or {}
    job_title = job_info.get("title") if isinstance(job_info, dict) else None
    job_company = job_info.get("company") if isinstance(job_info, dict) else None

    # Fetch results
    try:
        results_res = (
            client.table("assessment_results")
            .select("*")
            .eq("assessment_run_id", r_id_str)
            .execute()
        )
    except Exception as exc:
        logger.error(f"Error fetching results for run {run_id}: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving assessment results.")

    raw_results = results_res.data or []
    raw_summary = run_row.get("status_summary") or {}
    summary = AssessmentStatusSummary(**raw_summary) if isinstance(raw_summary, dict) else AssessmentStatusSummary()

    # Fail closed: Incomplete assessments must never be presented as successful evaluations
    if len(raw_results) == 0 and summary.total_requirements > 0:
        logger.error(f"Incomplete assessment run detected {run_id}: 0 results found but {summary.total_requirements} expected.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Incomplete assessment record: requirement evaluation results are missing for this snapshot.",
        )

    # Collect all evidence IDs across results to resolve them in bulk
    all_evidence_ids: List[str] = []
    for r in raw_results:
        ev_ids = r.get("evidence_ids") or []
        all_evidence_ids.extend(ev_ids)

    resolved_evidence: Dict[str, Dict[str, Any]] = {}
    if all_evidence_ids:
        try:
            ev_res = (
                client.table("skill_evidence")
                .select("*, repositories(name)")
                .in_("id", all_evidence_ids)
                .execute()
            )
            for row in ev_res.data or []:
                resolved_evidence[str(row["id"])] = row
        except Exception as exc:
            logger.warning(f"Error resolving evidence details: {exc}")

    results: List[AssessmentResultItem] = []
    for r in raw_results:
        ev_items: List[AssessmentEvidenceReference] = []
        for e_id in r.get("evidence_ids") or []:
            ev_data = resolved_evidence.get(str(e_id))
            if ev_data:
                repo_info = ev_data.get("repositories") or {}
                repo_name = repo_info.get("name") if isinstance(repo_info, dict) else None
                ev_items.append(
                    AssessmentEvidenceReference(
                        id=str(ev_data["id"]),
                        repository_id=str(ev_data.get("repository_id", "")),
                        repository_name=repo_name,
                        canonical_skill=ev_data.get("canonical_skill", ""),
                        file_path=ev_data.get("file_path", ""),
                        line_range=ev_data.get("line_range"),
                        commit_sha=ev_data.get("commit_sha", ""),
                        explanation=ev_data.get("explanation", ""),
                        evidence_type=ev_data.get("evidence_type", "ast_node"),
                        snippet=ev_data.get("snippet"),
                    )
                )

        results.append(
            AssessmentResultItem(
                id=str(r["id"]),
                requirement_id=r["requirement_id"],
                skill_name=r["skill_name"],
                category=r.get("category", "core_required"),
                status=r["status"],
                explanation=r["explanation"],
                evidence_ids=r.get("evidence_ids") or [],
                evidence_items=ev_items,
                limitations=r.get("limitations"),
                suggestion=r.get("suggestion"),
            )
        )

    raw_summary = run_row.get("status_summary") or {}
    summary = AssessmentStatusSummary(**raw_summary) if isinstance(raw_summary, dict) else AssessmentStatusSummary()

    return AssessmentRunResponse(
        id=r_id_str,
        portfolio_id=p_id_str,
        job_id=str(run_row["job_id"]),
        job_title=job_title,
        job_company=job_company,
        snapshot_number=run_row.get("snapshot_number", 1),
        trigger_type=run_row.get("trigger_type", "initial_scan"),
        commit_references=run_row.get("commit_references") or {},
        status_summary=summary,
        results=results,
        created_at=run_row.get("created_at", ""),
    )
