"""
ProofPath AI — Evidence-Based Assessment Engine
Evaluates target job requirements against ground-truth code evidence:
- Direct AST and code citations vs manifest/indirect citations
- Four PRD-mandated statuses: demonstrated | partially_demonstrated | not_demonstrated_in_scope | uncertain
- Grounded explanations citing exact files, line numbers, and commit SHAs
- Explicit declaration that absence of evidence in selected scope is NOT proof candidate lacks a skill
- Atomic snapshot number allocation for (portfolio_id, job_id)
- Respects database immutability triggers (ON DELETE RESTRICT, no updates/deletions)
"""
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from app.core.supabase import get_supabase_client
from app.schemas.assessment import (
    AssessmentEvidenceReference,
    AssessmentResultItem,
    AssessmentRunResponse,
    AssessmentStatusSummary,
    AssessmentStatusType,
)
from app.schemas.job import ExtractedRequirement

logger = logging.getLogger("proofpath_ai.assessment_engine")


class AssessmentEngineError(Exception):
    """Exception raised during assessment execution."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_token(text: str) -> str:
    """Normalizes a skill name or token for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def match_evidence_to_requirement(
    req: ExtractedRequirement,
    all_evidence: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Finds skill_evidence records that match an individual job requirement.
    Uses canonical_skill, tag tokens, and semantic keywords.
    """
    req_tokens: Set[str] = set()
    req_tokens.add(normalize_token(req.skill_name))
    for t in req.tags:
        req_tokens.add(normalize_token(t))

    words = re.findall(r"[A-Za-z0-9+#]+", req.skill_name)
    for w in words:
        if len(w) >= 3 and w.lower() not in ("and", "for", "the", "with", "services", "architecture"):
            req_tokens.add(normalize_token(w))

    matches: List[Dict[str, Any]] = []

    for ev in all_evidence:
        skill_clean = normalize_token(ev.get("canonical_skill", ""))
        file_path_clean = ev.get("file_path", "").lower()
        explanation_clean = ev.get("explanation", "").lower()

        # Direct token match
        is_match = False
        if skill_clean in req_tokens:
            is_match = True
        elif any(t in skill_clean for t in req_tokens if len(t) >= 4):
            is_match = True
        elif any(t in file_path_clean for t in req_tokens if len(t) >= 4):
            is_match = True
        elif any(t in explanation_clean for t in req_tokens if len(t) >= 5):
            is_match = True

        if is_match:
            matches.append(ev)

    return matches


def evaluate_requirement(
    req: ExtractedRequirement,
    matching_evidence: List[Dict[str, Any]],
    repo_map: Dict[str, str],
    total_scanned_repos: int,
) -> AssessmentResultItem:
    """
    Evaluates a single requirement against matched evidence to determine PRD status.
    """
    if not matching_evidence:
        return AssessmentResultItem(
            requirement_id=req.id,
            skill_name=req.skill_name,
            category=req.category,
            status="not_demonstrated_in_scope",
            explanation=(
                f"No supporting evidence found in the scanned repositories and files for '{req.skill_name}'. "
                "Note: Absence of evidence in selected repositories does not imply the candidate lacks this skill."
            ),
            evidence_ids=[],
            evidence_items=[],
            limitations=f"Evaluated across {total_scanned_repos} selected repositories.",
            suggestion=f"Consider committing a representative implementation or repository demonstrating '{req.skill_name}'.",
        )

    # Check evidence types: ast_node / code vs manifest / workflow
    ast_matches = [e for e in matching_evidence if e.get("evidence_type") == "ast_node"]
    manifest_matches = [e for e in matching_evidence if e.get("evidence_type") in ("manifest", "workflow", "file_match")]

    evidence_refs: List[AssessmentEvidenceReference] = []
    evidence_ids: List[str] = []

    for ev in matching_evidence:
        r_id = ev.get("repository_id", "")
        evidence_ids.append(str(ev["id"]))
        evidence_refs.append(
            AssessmentEvidenceReference(
                id=str(ev["id"]),
                repository_id=r_id,
                repository_name=repo_map.get(r_id, "repository"),
                canonical_skill=ev.get("canonical_skill", ""),
                file_path=ev.get("file_path", ""),
                line_range=ev.get("line_range"),
                commit_sha=ev.get("commit_sha", ""),
                explanation=ev.get("explanation", ""),
                evidence_type=ev.get("evidence_type", "ast_node"),
                snippet=ev.get("snippet"),
            )
        )

    if ast_matches:
        # Direct evidence in code AST
        first_ev = ast_matches[0]
        repo_name = repo_map.get(first_ev.get("repository_id", ""), "repository")
        line_ref = first_ev.get("line_range") or f"line {first_ev.get('line_start')}"
        explanation = (
            f"Demonstrated with direct code evidence in {repo_name} ({first_ev.get('file_path')}:{line_ref}). "
            f"{first_ev.get('explanation')}"
        )
        return AssessmentResultItem(
            requirement_id=req.id,
            skill_name=req.skill_name,
            category=req.category,
            status="demonstrated",
            explanation=explanation,
            evidence_ids=evidence_ids,
            evidence_items=evidence_refs,
            limitations=None,
            suggestion=f"Evidence is solid with {len(ast_matches)} direct code citations across scanned files.",
        )
    elif manifest_matches:
        # Indirect or declarative evidence (SQL schemas, package dependencies, CI/CD workflows)
        first_ev = manifest_matches[0]
        repo_name = repo_map.get(first_ev.get("repository_id", ""), "repository")

        if first_ev.get("canonical_skill") == "SQL" or first_ev.get("file_path", "").lower().endswith(".sql"):
            line_ref = first_ev.get("line_range") or f"L{first_ev.get('line_start', 1)}"
            explanation = (
                f"Found declarative database schema / SQL definition in {repo_name} ({first_ev.get('file_path')}:{line_ref}), "
                "demonstrating schema modeling and SQL construct definition, but application-level query integration logic was not detected in scanned code."
            )
            limitations = "Evidence grounded in declarative SQL schema and migration statements rather than application-layer ORM/query execution logic."
            suggestion = f"Consider connecting this SQL schema to application query handlers or services demonstrating runtime usage of '{req.skill_name}'."
        else:
            explanation = (
                f"Found configuration or dependency reference in {repo_name} ({first_ev.get('file_path')}), "
                "but direct programmatic application logic was not detected in scanned files."
            )
            limitations = "Evidence based on manifest/configuration declarations without AST function/class proofs."
            suggestion = f"Add core implementation logic using '{req.skill_name}' in application source files."

        return AssessmentResultItem(
            requirement_id=req.id,
            skill_name=req.skill_name,
            category=req.category,
            status="partially_demonstrated",
            explanation=explanation,
            evidence_ids=evidence_ids,
            evidence_items=evidence_refs,
            limitations=limitations,
            suggestion=suggestion,
        )
    else:
        # Ambiguous match
        return AssessmentResultItem(
            requirement_id=req.id,
            skill_name=req.skill_name,
            category=req.category,
            status="uncertain",
            explanation=f"Ambiguous evidence detected for '{req.skill_name}'. Unable to conclusively verify implementation.",
            evidence_ids=evidence_ids,
            evidence_items=evidence_refs,
            limitations="Match confidence is below definitive threshold.",
            suggestion="Refactor code structure to make pattern usage more inspectable.",
        )


class AssessmentService:
    """Service to execute evidence-based assessments and create immutable snapshots."""

    def __init__(self, supabase_client: Optional[Any] = None):
        self._supabase = supabase_client

    @property
    def supabase(self) -> Any:
        return self._supabase if self._supabase is not None else get_supabase_client()

    async def run_assessment(
        self,
        portfolio_id: UUID,
        job_id: UUID,
        trigger_type: str = "initial_scan",
        triggering_event_id: Optional[UUID] = None,
    ) -> AssessmentRunResponse:
        """
        Executes an assessment matching candidate's code evidence against target job requirements.
        Persists immutable snapshot in Supabase.
        Scoped to latest completed scan per repository to invalidate deleted/modified evidence.
        Safely retries on concurrent snapshot allocation conflict.
        """
        client = self.supabase
        p_id_str = str(portfolio_id)
        j_id_str = str(job_id)

        # 1. Fetch Job
        try:
            job_res = client.table("jobs").select("*").eq("id", j_id_str).execute()
        except Exception as exc:
            logger.error(f"Error fetching job {job_id}: {exc}")
            raise AssessmentEngineError("Database error retrieving target job.", status_code=500)

        if not job_res.data:
            raise AssessmentEngineError(f"Job with ID {job_id} not found.", status_code=404)

        job_data = job_res.data[0]
        job_title = job_data.get("title", "Target Role")
        job_company = job_data.get("company")

        raw_reqs = job_data.get("requirements") or []
        requirements = [ExtractedRequirement(**r) for r in raw_reqs if r.get("is_included", True)]

        if not requirements:
            raise AssessmentEngineError("No active requirements selected for this job description.", status_code=400)

        # 2. Fetch Selected Repositories for Portfolio
        try:
            repo_res = (
                client.table("repositories")
                .select("id, name, full_name, default_branch, last_commit_sha, is_selected")
                .eq("portfolio_id", p_id_str)
                .eq("is_selected", True)
                .execute()
            )
        except Exception as exc:
            logger.error(f"Error fetching repositories for portfolio {portfolio_id}: {exc}")
            raise AssessmentEngineError("Database error retrieving candidate repositories.", status_code=500)

        selected_repos = repo_res.data or []
        repo_ids = [r["id"] for r in selected_repos]
        repo_map = {r["id"]: r["name"] for r in selected_repos}
        commit_refs = {r["name"]: r.get("last_commit_sha") or "unknown" for r in selected_repos}

        # 3. Fetch Skill Evidence for Selected Repositories
        # Scope evidence to the latest completed scan per repository to prevent resurrecting deleted/stale code
        all_evidence: List[Dict[str, Any]] = []
        if repo_ids:
            latest_scan_ids: List[str] = []
            for r_id in repo_ids:
                try:
                    s_res = (
                        client.table("repository_scans")
                        .select("id, commit_sha")
                        .eq("repository_id", r_id)
                        .in_("status", ["completed", "partial"])
                        .order("started_at", desc=True)
                        .limit(1)
                        .execute()
                    )
                    if s_res and isinstance(s_res.data, list) and s_res.data:
                        scan_row = s_res.data[0]
                        if isinstance(scan_row, dict):
                            scan_id = scan_row.get("id")
                            if scan_id and isinstance(scan_id, (str, int)):
                                latest_scan_ids.append(str(scan_id))
                            repo_name = repo_map.get(r_id)
                            commit_val = scan_row.get("commit_sha")
                            if repo_name and isinstance(commit_val, str) and commit_val:
                                commit_refs[repo_name] = commit_val
                except Exception as exc:
                    logger.warning(f"Error checking latest scan for repo {r_id}: {exc}")

            try:
                if latest_scan_ids:
                    ev_res = (
                        client.table("skill_evidence")
                        .select("*")
                        .in_("scan_id", latest_scan_ids)
                        .execute()
                    )
                else:
                    # Fallback if scans exist by repository_id directly
                    ev_res = (
                        client.table("skill_evidence")
                        .select("*")
                        .in_("repository_id", repo_ids)
                        .execute()
                    )
                all_evidence = ev_res.data or []
            except Exception as exc:
                logger.error(f"Error fetching skill evidence for portfolio {portfolio_id}: {exc}")
                raise AssessmentEngineError("Database error retrieving skill evidence.", status_code=500)

        # 4. Evaluate each requirement
        results: List[AssessmentResultItem] = []
        demonstrated_count = 0
        partially_demonstrated_count = 0
        not_demonstrated_in_scope_count = 0
        uncertain_count = 0

        for req in requirements:
            matched_ev = match_evidence_to_requirement(req, all_evidence)
            result_item = evaluate_requirement(
                req=req,
                matching_evidence=matched_ev,
                repo_map=repo_map,
                total_scanned_repos=len(selected_repos),
            )
            results.append(result_item)

            if result_item.status == "demonstrated":
                demonstrated_count += 1
            elif result_item.status == "partially_demonstrated":
                partially_demonstrated_count += 1
            elif result_item.status == "not_demonstrated_in_scope":
                not_demonstrated_in_scope_count += 1
            else:
                uncertain_count += 1

        summary = AssessmentStatusSummary(
            demonstrated_count=demonstrated_count,
            partially_demonstrated_count=partially_demonstrated_count,
            not_demonstrated_in_scope_count=not_demonstrated_in_scope_count,
            uncertain_count=uncertain_count,
            total_requirements=len(requirements),
            scanned_repositories_count=len(selected_repos),
            total_evidence_count=len(all_evidence),
        )

        # 5 & 6. Persist immutable assessment_run with concurrency retry loop
        max_retries = 3
        run_insert = None
        snapshot_number = 1

        for attempt in range(max_retries):
            try:
                prev_runs = (
                    client.table("assessment_runs")
                    .select("snapshot_number")
                    .eq("portfolio_id", p_id_str)
                    .eq("job_id", j_id_str)
                    .order("snapshot_number", desc=True)
                    .limit(1)
                    .execute()
                )
                latest_num = prev_runs.data[0]["snapshot_number"] if prev_runs.data else 0
                snapshot_number = latest_num + 1

                insert_payload: Dict[str, Any] = {
                    "portfolio_id": p_id_str,
                    "job_id": j_id_str,
                    "snapshot_number": snapshot_number,
                    "trigger_type": trigger_type,
                    "commit_references": commit_refs,
                    "status_summary": summary.model_dump(),
                }
                if triggering_event_id:
                    insert_payload["triggering_event_id"] = str(triggering_event_id)

                run_insert = (
                    client.table("assessment_runs")
                    .insert(insert_payload)
                    .execute()
                )
                if run_insert.data:
                    break
            except Exception as exc:
                err_msg = str(exc).lower()
                # Check for unique constraint conflict on (portfolio_id, job_id, snapshot_number)
                if ("duplicate key" in err_msg or "uq_assessment_runs_snapshot" in err_msg or "conflict" in err_msg or "unique" in err_msg) and attempt < max_retries - 1:
                    logger.warning(f"Concurrent snapshot collision for ({p_id_str}, {j_id_str}, snapshot {snapshot_number}). Retrying attempt {attempt + 1}...")
                    continue
                logger.error(f"Error persisting assessment run: {exc}")
                raise AssessmentEngineError("Failed to persist immutable assessment snapshot.", status_code=500)

        if not run_insert or not run_insert.data:
            raise AssessmentEngineError("No data returned from assessment run creation.", status_code=500)

        run_row = run_insert.data[0]
        run_id = str(run_row["id"])

        # 7. Insert child assessment_results records
        results_to_insert = [
            {
                "assessment_run_id": run_id,
                "requirement_id": r.requirement_id,
                "skill_name": r.skill_name,
                "category": r.category,
                "status": r.status,
                "explanation": r.explanation,
                "evidence_ids": r.evidence_ids,
                "limitations": r.limitations,
                "suggestion": r.suggestion,
            }
            for r in results
        ]

        if results_to_insert:
            try:
                res_insert = client.table("assessment_results").insert(results_to_insert).execute()
                # Attach persisted IDs to results
                for idx, saved_res in enumerate(res_insert.data or []):
                    if idx < len(results):
                        results[idx].id = str(saved_res["id"])
            except Exception as exc:
                logger.error(f"Error persisting assessment results for run {run_id}: {exc}")
                # Fail closed: Do NOT present incomplete assessment run as valid
                raise AssessmentEngineError(
                    "Failed to persist requirement assessment results. Snapshot results incomplete.",
                    status_code=500,
                )

        return AssessmentRunResponse(
            id=run_id,
            portfolio_id=p_id_str,
            job_id=j_id_str,
            job_title=job_title,
            job_company=job_company,
            snapshot_number=snapshot_number,
            trigger_type=trigger_type,
            commit_references=commit_refs,
            status_summary=summary,
            results=results,
            created_at=run_row.get("created_at", ""),
        )


_assessment_service = AssessmentService()


def get_assessment_service() -> AssessmentService:
    """Returns singleton assessment service instance."""
    return _assessment_service
