"""
ProofPath AI — Bounded Repository Scanner Engine
Coordinates deterministic, bounded code scanning pinned to immutable commit SHAs:
- Bounded concurrency, file limits, and 30-second execution ceilings
- Commit SHA resolution and tree pinning (no branch drift)
- Eligibility filtering and secret-path exclusion
- Ground-truth evidence extraction via EvidenceExtractor
- Supabase relational persistence for repository_scans and skill_evidence
- Partial failure isolation (failure in one repo does not invalidate others)
- Duplicate scan prevention
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.config import settings
from app.core.supabase import get_supabase_client
from app.services.github_client import (
    GitHubClient,
    get_github_client,
    GitHubClientError,
    GitHubRateLimitError,
)
from app.services.evidence_extractor import (
    EvidenceExtractor,
    is_file_eligible,
)

logger = logging.getLogger("proofpath_ai.scanner")


class ScannerError(Exception):
    """Base exception for repository scanning errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RepositoryScanner:
    """
    Executes bounded, authenticated/unauthenticated code scanning on selected candidate repositories.
    """
    def __init__(
        self,
        github_client: Optional[GitHubClient] = None,
        supabase_client: Optional[Any] = None,
    ):
        self.github = github_client or get_github_client()
        self.supabase = supabase_client or get_supabase_client()

    async def scan_portfolio(
        self,
        portfolio_id: UUID,
        repository_ids: Optional[List[UUID]] = None,
    ) -> Dict[str, Any]:
        """
        Scans all selected (or explicitly requested) repositories for a portfolio.
        Returns consolidated scan telemetry.
        """
        p_id_str = str(portfolio_id)

        # 1. Check portfolio state
        p_res = (
            self.supabase.table("portfolios")
            .select("id, scan_status, is_archived")
            .eq("id", p_id_str)
            .execute()
        )
        if not p_res.data:
            raise ScannerError("Portfolio not found.", status_code=404)

        portfolio_row = p_res.data[0]
        if portfolio_row.get("is_archived"):
            raise ScannerError("Cannot scan an archived portfolio.", status_code=403)

        # Prevent duplicate concurrent scans
        if portfolio_row.get("scan_status") == "scanning":
            logger.info(f"Scan already in progress for portfolio {p_id_str}")
            # Fetch and return active scan status rather than launching duplicate
            return await self.get_portfolio_scan_status(portfolio_id)

        # 2. Fetch selected repositories
        query = (
            self.supabase.table("repositories")
            .select("id, portfolio_id, name, full_name, default_branch, is_selected, is_eligible")
            .eq("portfolio_id", p_id_str)
        )
        if repository_ids:
            id_strs = [str(r_id) for r_id in repository_ids]
            query = query.in_("id", id_strs)
        else:
            query = query.eq("is_selected", True)

        repos_res = query.execute()
        target_repos = repos_res.data or []

        if not target_repos:
            raise ScannerError("No eligible repositories selected for scanning.", status_code=400)

        # Mark portfolio as 'scanning'
        self.supabase.table("portfolios").update({
            "scan_status": "scanning",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", p_id_str).execute()

        scan_telemetry: List[Dict[str, Any]] = []
        overall_successes = 0
        overall_failures = 0

        for repo in target_repos:
            try:
                # Enforce per-repository scan timeout
                telemetry = await asyncio.wait_for(
                    self._scan_single_repository(repo),
                    timeout=settings.SCAN_TIMEOUT_SECONDS,
                )
                scan_telemetry.append(telemetry)
                if telemetry["status"] in ("completed", "partial"):
                    overall_successes += 1
                else:
                    overall_failures += 1
            except asyncio.TimeoutError:
                logger.error(f"Scan timed out after {settings.SCAN_TIMEOUT_SECONDS}s for repo {repo['full_name']}")
                failed_item = await self._record_failed_scan(
                    repo=repo,
                    commit_sha="unknown",
                    reason=f"Scan exceeded safety timeout ceiling of {settings.SCAN_TIMEOUT_SECONDS}s.",
                )
                scan_telemetry.append(failed_item)
                overall_failures += 1
            except Exception as exc:
                logger.error(f"Scan failed for repository {repo.get('full_name')}: {exc}")
                failed_item = await self._record_failed_scan(
                    repo=repo,
                    commit_sha="unknown",
                    reason=f"Scan error: {str(exc)[:500]}",
                )
                scan_telemetry.append(failed_item)
                overall_failures += 1

        # Determine final portfolio scan status
        if overall_successes > 0 and overall_failures == 0:
            final_status = "completed"
        elif overall_successes > 0 and overall_failures > 0:
            final_status = "partial"
        else:
            final_status = "failed"

        self.supabase.table("portfolios").update({
            "scan_status": final_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", p_id_str).execute()

        # Count total evidence
        evidence_count = 0
        for scan in scan_telemetry:
            scan_id = scan.get("scan_id")
            if scan_id:
                count_res = (
                    self.supabase.table("skill_evidence")
                    .select("id", count="exact")
                    .eq("scan_id", scan_id)
                    .execute()
                )
                evidence_count += count_res.count if hasattr(count_res, "count") and count_res.count is not None else len(count_res.data or [])

        return {
            "portfolio_id": p_id_str,
            "portfolio_status": final_status,
            "total_repositories_selected": len(target_repos),
            "scans_completed": overall_successes,
            "scans_running": 0,
            "scans_failed": overall_failures,
            "total_evidence_count": evidence_count,
            "scans": scan_telemetry,
        }

    async def scan_single_repository(
        self,
        repo: Dict[str, Any],
        commit_sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes bounded scanning for one repository, optionally pinned to an explicit commit SHA.
        Used by GitHub webhook ingestion and incremental refresh.
        """
        return await self._scan_single_repository(repo, commit_sha=commit_sha)

    async def _scan_single_repository(
        self,
        repo: Dict[str, Any],
        commit_sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes bounded scanning for one repository pinned to a commit SHA.
        """
        repo_id = str(repo["id"])
        full_name = repo["full_name"]
        default_branch = repo.get("default_branch") or "main"

        parts = full_name.split("/")
        if len(parts) != 2:
            raise ScannerError(f"Malformed repository full_name: {full_name}")
        owner, repo_name = parts[0], parts[1]

        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()

        # Step 1: Resolve branch commit SHA if not explicitly provided
        if not commit_sha:
            try:
                commit_sha = await self.github.get_latest_commit_sha(owner, repo_name, default_branch)
            except GitHubClientError as exc:
                return await self._record_failed_scan(repo, "unknown", f"Commit resolution failed: {exc.message}")

        # Step 2: Initialize scan record in database
        scan_insert = (
            self.supabase.table("repository_scans")
            .insert({
                "repository_id": repo_id,
                "commit_sha": commit_sha,
                "status": "running",
                "files_processed": 0,
                "total_files": 0,
                "started_at": started_at,
            })
            .execute()
        )
        scan_id = scan_insert.data[0]["id"]

        # Step 3: Fetch Git tree pinned to commit_sha
        try:
            tree = await self.github.get_git_tree(owner, repo_name, commit_sha, recursive=True)
        except GitHubClientError as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            self.supabase.table("repository_scans").update({
                "status": "failed",
                "skipped_summary": f"Tree fetch failed: {exc.message}",
                "duration_ms": duration_ms,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", scan_id).execute()
            return {
                "scan_id": scan_id,
                "repository_id": repo_id,
                "repository_name": full_name,
                "commit_sha": commit_sha,
                "status": "failed",
                "files_processed": 0,
                "total_files": 0,
                "skipped_summary": f"Tree fetch failed: {exc.message}",
                "duration_ms": duration_ms,
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

        # Step 4: Evaluate file eligibility and enforce file budget
        eligible_items = []
        skipped_count = 0
        total_tree_files = len(tree)

        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            size = item.get("size", 0)

            eligible, reason = is_file_eligible(path, size, settings.MAX_FILE_SIZE_BYTES)
            if eligible:
                if len(eligible_items) < settings.MAX_FILES_PER_REPO:
                    eligible_items.append(item)
                else:
                    skipped_count += 1
            else:
                skipped_count += 1

        # Step 5: Bounded file download & evidence extraction
        semaphore = asyncio.Semaphore(5)
        extracted_evidence: List[Dict[str, Any]] = []
        downloaded_bytes = 0
        processed_files = 0
        file_download_errors = 0

        async def fetch_and_extract(item: Dict[str, Any]) -> None:
            nonlocal downloaded_bytes, processed_files, file_download_errors
            if downloaded_bytes >= settings.MAX_TOTAL_REPO_BYTES:
                return

            path = item.get("path", "")
            blob_sha = item.get("sha", "")

            async with semaphore:
                try:
                    content, size = await self.github.get_blob_content(
                        owner,
                        repo_name,
                        blob_sha,
                        max_bytes=settings.MAX_FILE_SIZE_BYTES,
                    )
                    downloaded_bytes += size
                    processed_files += 1

                    items = EvidenceExtractor.extract_evidence(path, content, commit_sha)
                    for ev in items:
                        ev["scan_id"] = scan_id
                        ev["repository_id"] = repo_id
                        extracted_evidence.append(ev)
                except Exception as exc:
                    logger.warning(f"Error reading {path} in {full_name}: {exc}")
                    file_download_errors += 1

        # Execute concurrent file extraction
        await asyncio.gather(*[fetch_and_extract(item) for item in eligible_items])

        # Step 6: Persist extracted evidence into Supabase
        if extracted_evidence:
            # Batch insert evidence records
            self.supabase.table("skill_evidence").insert(extracted_evidence).execute()

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        completed_at = datetime.now(timezone.utc).isoformat()

        # Update repository's last_commit_sha
        self.supabase.table("repositories").update({
            "last_commit_sha": commit_sha,
        }).eq("id", repo_id).execute()

        scan_status = "completed"
        skipped_summary = f"Processed {processed_files} files ({downloaded_bytes} bytes). Skipped {skipped_count} files."
        if file_download_errors > 0:
            scan_status = "partial"
            skipped_summary += f" Encountered {file_download_errors} file download issues."
        elif not eligible_items and total_tree_files > 0:
            skipped_summary = "No qualifying source files matched eligibility criteria."

        # Step 7: Update scan record
        self.supabase.table("repository_scans").update({
            "status": scan_status,
            "files_processed": processed_files,
            "total_files": len(eligible_items),
            "skipped_summary": skipped_summary[:1000],
            "duration_ms": duration_ms,
            "completed_at": completed_at,
        }).eq("id", scan_id).execute()

        # Update last_commit_sha on repository record ONLY on successful completed/partial scan
        if scan_status in ("completed", "partial"):
            try:
                self.supabase.table("repositories").update({
                    "last_commit_sha": commit_sha,
                }).eq("id", repo_id).execute()
            except Exception as exc:
                logger.warning(f"Failed to update last_commit_sha on repository {repo_id}: {exc}")

        return {
            "scan_id": scan_id,
            "repository_id": repo_id,
            "repository_name": full_name,
            "commit_sha": commit_sha,
            "status": scan_status,
            "files_processed": processed_files,
            "total_files": len(eligible_items),
            "skipped_summary": skipped_summary,
            "duration_ms": duration_ms,
            "started_at": started_at,
            "completed_at": completed_at,
        }

    async def _record_failed_scan(
        self,
        repo: Dict[str, Any],
        commit_sha: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Helper to create and persist a failed scan record."""
        repo_id = str(repo["id"])
        now = datetime.now(timezone.utc).isoformat()
        scan_insert = (
            self.supabase.table("repository_scans")
            .insert({
                "repository_id": repo_id,
                "commit_sha": commit_sha,
                "status": "failed",
                "files_processed": 0,
                "total_files": 0,
                "skipped_summary": reason[:1000],
                "duration_ms": 0,
                "started_at": now,
                "completed_at": now,
            })
            .execute()
        )
        scan_id = scan_insert.data[0]["id"]
        return {
            "scan_id": scan_id,
            "repository_id": repo_id,
            "repository_name": repo.get("full_name", ""),
            "commit_sha": commit_sha,
            "status": "failed",
            "files_processed": 0,
            "total_files": 0,
            "skipped_summary": reason,
            "duration_ms": 0,
            "started_at": now,
            "completed_at": now,
        }

    async def get_portfolio_scan_status(self, portfolio_id: UUID) -> Dict[str, Any]:
        """
        Retrieves real, persisted scan telemetry and status for a portfolio.
        """
        p_id_str = str(portfolio_id)

        # 1. Fetch portfolio status
        p_res = (
            self.supabase.table("portfolios")
            .select("id, scan_status")
            .eq("id", p_id_str)
            .execute()
        )
        if not p_res.data:
            raise ScannerError("Portfolio not found.", status_code=404)
        p_status = p_res.data[0].get("scan_status", "pending")

        # 2. Fetch selected repositories
        repos_res = (
            self.supabase.table("repositories")
            .select("id, full_name, is_selected")
            .eq("portfolio_id", p_id_str)
            .execute()
        )
        repos = repos_res.data or []
        repo_map = {r["id"]: r["full_name"] for r in repos}
        selected_repos = [r for r in repos if r.get("is_selected")]

        # 3. Fetch latest scan for each repository
        repo_ids = list(repo_map.keys())
        scans_list: List[Dict[str, Any]] = []
        completed_count = 0
        running_count = 0
        failed_count = 0

        if repo_ids:
            scans_res = (
                self.supabase.table("repository_scans")
                .select("id, repository_id, commit_sha, status, files_processed, total_files, skipped_summary, duration_ms, started_at, completed_at")
                .in_("repository_id", repo_ids)
                .order("started_at", desc=True)
                .execute()
            )
            raw_scans = scans_res.data or []

            # Keep only the latest scan per repository
            seen_repo_ids = set()
            for s in raw_scans:
                r_id = s["repository_id"]
                if r_id not in seen_repo_ids:
                    seen_repo_ids.add(r_id)
                    s_status = s.get("status", "queued")
                    if s_status == "completed":
                        completed_count += 1
                    elif s_status in ("running", "queued"):
                        running_count += 1
                    elif s_status in ("failed", "partial"):
                        failed_count += 1

                    scans_list.append({
                        "scan_id": s["id"],
                        "repository_id": r_id,
                        "repository_name": repo_map.get(r_id, "Unknown"),
                        "commit_sha": s.get("commit_sha", ""),
                        "status": s_status,
                        "files_processed": s.get("files_processed", 0),
                        "total_files": s.get("total_files", 0),
                        "skipped_summary": s.get("skipped_summary"),
                        "duration_ms": s.get("duration_ms"),
                        "started_at": s.get("started_at", ""),
                        "completed_at": s.get("completed_at"),
                    })

        # 4. Count total evidence items for portfolio
        evidence_count = 0
        if scans_list:
            scan_ids = [s["scan_id"] for s in scans_list]
            ev_count_res = (
                self.supabase.table("skill_evidence")
                .select("id", count="exact")
                .in_("scan_id", scan_ids)
                .execute()
            )
            evidence_count = ev_count_res.count if hasattr(ev_count_res, "count") and ev_count_res.count is not None else len(ev_count_res.data or [])

        return {
            "portfolio_id": p_id_str,
            "portfolio_status": p_status,
            "total_repositories_selected": len(selected_repos),
            "scans_completed": completed_count,
            "scans_running": running_count,
            "scans_failed": failed_count,
            "total_evidence_count": evidence_count,
            "scans": scans_list,
        }
