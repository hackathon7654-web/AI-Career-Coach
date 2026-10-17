"""
ProofPath AI — GitHub Webhook Processing Service
Coordinates HMAC verification, idempotent ledgering, repository identity verification,
bounded scanning, and automatic evidence-based reassessment.
"""
import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from app.core.config import settings
from app.core.supabase import get_supabase_client
from app.schemas.webhook import (
    GitHubPushPayload,
    WebhookDeliveryItem,
    WebhookResponse,
)
from app.services.assessment_engine import get_assessment_service
from app.services.repository_scanner import RepositoryScanner

logger = logging.getLogger("proofpath_ai.webhooks")

HEX_SHA_REGEX = re.compile(r"^[0-9a-fA-F]{40}$")
ZERO_SHA = "0000000000000000000000000000000000000000"


class WebhookVerificationError(Exception):
    """Raised when webhook signature verification fails."""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def verify_github_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Validates GitHub HMAC-SHA256 signature using constant-time comparison.
    Fails closed if the secret is unconfigured, header is missing, or digest mismatches.
    Never logs secrets or signatures.
    """
    secret = settings.GITHUB_WEBHOOK_SECRET
    if not secret:
        logger.error("GitHub webhook rejected: GITHUB_WEBHOOK_SECRET is not configured on the server.")
        raise WebhookVerificationError(
            "Webhook processing disabled: server webhook secret is not configured.",
            status_code=500,
        )

    if not signature_header:
        raise WebhookVerificationError(
            "Authentication required: missing X-Hub-Signature-256 header.",
            status_code=401,
        )

    if not signature_header.startswith("sha256="):
        raise WebhookVerificationError(
            "Invalid signature format: expected sha256=<hex_digest>.",
            status_code=401,
        )

    expected_digest = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    expected_header = f"sha256={expected_digest}"

    if not hmac.compare_digest(expected_header, signature_header):
        raise WebhookVerificationError(
            "Signature verification failed: invalid HMAC-SHA256 digest.",
            status_code=401,
        )

    return True


class WebhookService:
    """Processes verified GitHub webhook events with idempotency and isolation."""

    def __init__(
        self,
        supabase_client: Optional[Any] = None,
        scanner: Optional[RepositoryScanner] = None,
        assessment_service: Optional[Any] = None,
    ):
        self._supabase = supabase_client
        self._scanner = scanner
        self._assessment_service = assessment_service

    @property
    def supabase(self) -> Any:
        return self._supabase if self._supabase is not None else get_supabase_client()

    @property
    def scanner(self) -> RepositoryScanner:
        return self._scanner if self._scanner is not None else RepositoryScanner(supabase_client=self.supabase)

    @property
    def assessment_service(self) -> Any:
        return self._assessment_service if self._assessment_service is not None else get_assessment_service()

    async def handle_push_event(
        self,
        delivery_id: str,
        raw_body: bytes,
        hmac_verified: bool = True,
    ) -> WebhookResponse:
        """
        Executes complete webhook ingestion pipeline:
        1. Idempotency deduplication via delivery_id
        2. Payload validation (ref, SHA, deleted branch checks)
        3. Repository identity resolution & cross-portfolio isolation
        4. Durable ledger persistence in repository_events
        5. Bounded scan of changed repository at target commit SHA
        6. Automatic reassessment of all active jobs for the portfolio
        7. Immutable assessment snapshot creation with triggering_event_id
        """
        client = self.supabase

        # Step 1: Idempotency & recovery check against existing repository_events
        is_recovery = False
        event_id = None
        retry_count = 0

        try:
            existing_res = (
                client.table("repository_events")
                .select("id, delivery_id, repository_name, commit_sha, status, reassessment_run_id, created_at, received_at, retry_count")
                .eq("delivery_id", delivery_id)
                .execute()
            )
            if existing_res.data:
                existing = existing_res.data[0]
                ev_status = existing.get("status")

                if ev_status == "completed":
                    logger.info(f"Duplicate completed webhook delivery ignored: {delivery_id}")
                    return WebhookResponse(
                        delivery_id=delivery_id,
                        status="duplicate",
                        repository=existing.get("repository_name"),
                        commit_sha=existing.get("commit_sha"),
                        reassessment_run_id=existing.get("reassessment_run_id"),
                        message="Delivery already processed successfully.",
                    )

                # Check if stuck in 'processing' beyond 5 minutes (300s)
                is_stuck_processing = False
                if ev_status == "processing":
                    raw_ts = existing.get("received_at") or existing.get("created_at")
                    if raw_ts:
                        try:
                            ts_clean = raw_ts.replace("Z", "+00:00")
                            event_time = datetime.fromisoformat(ts_clean)
                            elapsed = (datetime.now(timezone.utc) - event_time).total_seconds()
                            if elapsed > 300:  # 5 minutes ceiling
                                is_stuck_processing = True
                        except Exception:
                            is_stuck_processing = True

                curr_retries = existing.get("retry_count", 0)
                can_recover = (is_stuck_processing or ev_status == "failed") and curr_retries < 3

                if not can_recover:
                    logger.info(f"Delivery {delivery_id} in flight or maximum retries reached (status={ev_status}, retries={curr_retries})")
                    return WebhookResponse(
                        delivery_id=delivery_id,
                        status="duplicate",
                        repository=existing.get("repository_name"),
                        commit_sha=existing.get("commit_sha"),
                        reassessment_run_id=existing.get("reassessment_run_id"),
                        message="Delivery currently in progress or maximum retry limit reached.",
                    )

                logger.warning(f"Recovering abandoned/failed delivery {delivery_id} (status={ev_status}, retry={curr_retries + 1})")
                is_recovery = True
                event_id = existing["id"]
                retry_count = curr_retries
        except Exception as exc:
            logger.error(f"Error checking delivery idempotency for {delivery_id}: {exc}")
            raise

        # Step 2: Parse and validate JSON payload
        try:
            payload_dict = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise WebhookVerificationError("Malformed JSON payload in request body.", status_code=400)

        # Handle branch deletions and empty after SHAs safely
        is_deleted = payload_dict.get("deleted", False)
        after_sha = payload_dict.get("after")
        ref = payload_dict.get("ref", "")
        repo_data = payload_dict.get("repository") or {}
        repo_full_name = repo_data.get("full_name")

        if not repo_full_name:
            raise WebhookVerificationError("Webhook payload missing repository full_name.", status_code=400)

        if is_deleted or not after_sha or after_sha == ZERO_SHA:
            logger.info(f"Ignored branch deletion event for {repo_full_name} on ref {ref}")
            return WebhookResponse(
                delivery_id=delivery_id,
                status="ignored",
                repository=repo_full_name,
                message="Branch deletion event ignored safely.",
            )

        if not HEX_SHA_REGEX.match(after_sha):
            raise WebhookVerificationError(f"Invalid target commit SHA format: {after_sha}", status_code=400)

        # Collect changed paths from commits
        changed_paths_set: Set[str] = set()
        for c in payload_dict.get("commits", []):
            changed_paths_set.update(c.get("added", []))
            changed_paths_set.update(c.get("modified", []))
            changed_paths_set.update(c.get("removed", []))
        head_c = payload_dict.get("head_commit")
        if head_c:
            changed_paths_set.update(head_c.get("added", []))
            changed_paths_set.update(head_c.get("modified", []))
            changed_paths_set.update(head_c.get("removed", []))
        changed_paths = sorted(list(changed_paths_set))

        # Step 3: Repository identity & cross-portfolio isolation
        # Query repositories table for matching full_name
        try:
            repo_res = (
                client.table("repositories")
                .select("id, portfolio_id, name, full_name, default_branch, is_selected, is_eligible")
                .eq("full_name", repo_full_name)
                .execute()
            )
            matching_repos = repo_res.data or []
        except Exception as exc:
            logger.error(f"Error querying repository {repo_full_name}: {exc}")
            raise

        if not matching_repos:
            logger.info(f"Webhook received for untracked repository: {repo_full_name}")
            return WebhookResponse(
                delivery_id=delivery_id,
                status="ignored",
                repository=repo_full_name,
                commit_sha=after_sha,
                message="Repository is not tracked by any candidate portfolio.",
            )

        # Filter for repositories that are both eligible and explicitly selected by a candidate
        selected_matching_repos = [
            r for r in matching_repos
            if r.get("is_selected") is True and r.get("is_eligible") is True
        ]

        if not selected_matching_repos:
            logger.info(f"Webhook received for unselected or ineligible repository: {repo_full_name}")
            return WebhookResponse(
                delivery_id=delivery_id,
                status="ignored",
                repository=repo_full_name,
                commit_sha=after_sha,
                message="Repository is not selected for evaluation by any candidate portfolio.",
            )

        # Step 4: Durable Event Ledgering
        if is_recovery and event_id:
            try:
                client.table("repository_events").update({
                    "status": "processing",
                    "commit_sha": after_sha,
                    "changed_paths": changed_paths,
                    "retry_count": retry_count + 1,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "error_details": None,
                }).eq("id", event_id).execute()
            except Exception as exc:
                logger.error(f"Failed to update repository_event during recovery for {delivery_id}: {exc}")
        else:
            event_row = None
            try:
                event_insert = (
                    client.table("repository_events")
                    .insert({
                        "delivery_id": delivery_id,
                        "repository_name": repo_full_name,
                        "event_type": "push",
                        "commit_sha": after_sha,
                        "changed_paths": changed_paths,
                        "hmac_verified": hmac_verified,
                        "status": "processing",
                        "retry_count": 0,
                    })
                    .execute()
                )
                if event_insert.data:
                    event_row = event_insert.data[0]
                    event_id = event_row["id"]
            except Exception as exc:
                err_str = str(exc).lower()
                if "duplicate key" in err_str or "delivery_id" in err_str:
                    logger.info(f"Concurrent delivery ID collision on {delivery_id}, returning duplicate.")
                    return WebhookResponse(
                        delivery_id=delivery_id,
                        status="duplicate",
                        repository=repo_full_name,
                        commit_sha=after_sha,
                        message="Delivery already processed or in progress.",
                    )
                logger.error(f"Failed to ledger repository_event for {delivery_id}: {exc}")
                raise
        latest_reassessment_run_id = None
        scans_executed = 0

        # Step 5 & 6: Scan and Reassess for each candidate portfolio tracking this repo
        try:
            for repo in selected_matching_repos:
                portfolio_id = repo["portfolio_id"]
                default_branch = repo.get("default_branch") or "main"
                expected_ref = f"refs/heads/{default_branch}"

                # Only trigger on default branch pushes unless configured otherwise
                if ref and ref != expected_ref and not ref.endswith(f"/{default_branch}"):
                    logger.info(f"Push ref '{ref}' does not match default branch '{default_branch}'. Skipping reassessment.")
                    continue

                # 5. Scan repository at after_sha
                logger.info(f"Executing bounded scan for {repo_full_name} at commit {after_sha}...")
                scan_result = await self.scanner.scan_single_repository(repo, commit_sha=after_sha)
                scans_executed += 1

                # If scan failed, do not claim successful evaluation
                if scan_result.get("status") == "failed":
                    logger.warning(f"Scan failed for repository {repo_full_name} at commit {after_sha}. Halting reassessment.")
                    if event_id:
                        try:
                            client.table("repository_events").update({
                                "status": "failed",
                                "error_details": f"Scan failed: {scan_result.get('skipped_summary', 'Unknown error')}",
                            }).eq("id", event_id).execute()
                        except Exception:
                            pass
                    return WebhookResponse(
                        delivery_id=delivery_id,
                        status="failed",
                        repository=repo_full_name,
                        commit_sha=after_sha,
                        message=f"Scan failed on pushed commit: {scan_result.get('skipped_summary', 'Unknown error')[:200]}",
                    )

                # 6. Reassess applicable active jobs for this candidate portfolio
                runs_query = (
                    client.table("assessment_runs")
                    .select("job_id")
                    .eq("portfolio_id", portfolio_id)
                    .execute()
                )
                existing_job_ids = list({r["job_id"] for r in (runs_query.data or [])})

                for job_id_str in existing_job_ids:
                    logger.info(f"Running automatic reassessment for portfolio {portfolio_id} on job {job_id_str}...")
                    run = await self.assessment_service.run_assessment(
                        portfolio_id=UUID(portfolio_id),
                        job_id=UUID(job_id_str),
                        trigger_type="webhook_push",
                        triggering_event_id=UUID(event_id) if event_id else None,
                    )
                    latest_reassessment_run_id = run.id

            if scans_executed == 0:
                if event_id:
                    client.table("repository_events").update({
                        "status": "ignored",
                    }).eq("id", event_id).execute()
                return WebhookResponse(
                    delivery_id=delivery_id,
                    status="ignored",
                    repository=repo_full_name,
                    commit_sha=after_sha,
                    message=f"Push ref '{ref}' did not target eligible default branch.",
                )

            # Step 7: Mark delivery as completed
            if event_id:
                client.table("repository_events").update({
                    "status": "completed",
                    "reassessment_run_id": latest_reassessment_run_id,
                }).eq("id", event_id).execute()

            return WebhookResponse(
                delivery_id=delivery_id,
                status="completed",
                repository=repo_full_name,
                commit_sha=after_sha,
                reassessment_run_id=latest_reassessment_run_id,
                message="Webhook push processed, evidence refreshed, and automatic reassessment completed.",
            )

        except Exception as exc:
            logger.error(f"Error processing webhook delivery {delivery_id}: {exc}")
            if event_id:
                try:
                    client.table("repository_events").update({
                        "status": "failed",
                        "error_details": str(exc)[:2000],
                    }).eq("id", event_id).execute()
                except Exception:
                    pass
            return WebhookResponse(
                delivery_id=delivery_id,
                status="failed",
                repository=repo_full_name,
                commit_sha=after_sha,
                message=f"Webhook processing failed: {str(exc)[:200]}",
            )

    async def recover_stuck_deliveries(self, timeout_seconds: int = 300) -> int:
        """
        Scans for deliveries abandoned in 'processing' status beyond timeout_seconds (default 300s / 5m),
        and safely transitions them to 'failed' with diagnostic details so they can be recovered/retried.
        Returns count of recovered events.
        """
        client = self.supabase
        try:
            cutoff = datetime.now(timezone.utc).timestamp() - timeout_seconds
            res = (
                client.table("repository_events")
                .select("id, delivery_id, received_at, retry_count")
                .eq("status", "processing")
                .execute()
            )
            recovered = 0
            for row in (res.data or []):
                raw_ts = row.get("received_at")
                if raw_ts:
                    try:
                        ts_clean = raw_ts.replace("Z", "+00:00")
                        ev_dt = datetime.fromisoformat(ts_clean)
                        if ev_dt.timestamp() < cutoff:
                            client.table("repository_events").update({
                                "status": "failed",
                                "error_details": f"Delivery abandoned in processing state for >{timeout_seconds}s. Flagged for retry.",
                            }).eq("id", row["id"]).execute()
                            recovered += 1
                    except Exception:
                        pass
            return recovered
        except Exception as exc:
            logger.warning(f"Error checking stuck deliveries: {exc}")
            return 0



_webhook_service: Optional[WebhookService] = None


def get_webhook_service() -> WebhookService:
    """Returns singleton WebhookService instance."""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service
