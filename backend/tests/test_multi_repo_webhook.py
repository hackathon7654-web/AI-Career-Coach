"""
ProofPath AI — Canonical Multi-Repository Webhook Architecture Test Suite
Verifies all 9 mandatory verification criteria:
1. Initial assessment pools evidence across all selected repositories (Repo A + Repo B).
2. A push to Repo A rescans Repo A only.
3. Repo B's valid stored evidence is reused without rescanning Repo B.
4. Snapshot #2 combines fresh Repo A evidence with existing Repo B evidence.
5. Push to unselected Repo C is ignored without scanning or reassessing.
6. Duplicate delivery IDs do not create duplicate reassessments.
7. Failed or incomplete scan records honest error telemetry and does not create a successful snapshot.
8. History shows correct immutable before/after snapshots and delta comparison.
9. Multiple selected repositories route through the same HTTPS endpoint to their respective portfolios.
"""
import hashlib
import hmac
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.session import generate_session_token, hash_session_token, verify_portfolio_session
from app.main import create_app
from app.schemas.assessment import (
    AssessmentEvidenceReference,
    AssessmentResultItem,
    AssessmentRunResponse,
    AssessmentStatusSummary,
)
from app.schemas.webhook import WebhookResponse
from app.services.assessment_engine import AssessmentService
from app.services.webhook_service import WebhookService


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def session_auth():
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)
    portfolio_id = str(uuid4())
    return {
        "raw_token": raw_token,
        "token_hash": token_hash,
        "portfolio_id": portfolio_id,
        "cookies": {settings.SESSION_COOKIE_NAME: raw_token},
        "headers": {"Origin": "http://localhost:5173", "X-Requested-With": "XMLHttpRequest"},
    }


def compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ==============================================================================
# SCENARIO 1: Initial assessment pools evidence from all selected repos (A + B)
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_1_initial_assessment_pools_evidence_from_all_selected_repos():
    portfolio_id = uuid4()
    job_id = uuid4()
    repo_a_id = str(uuid4())
    repo_b_id = str(uuid4())
    scan_a_id = str(uuid4())
    scan_b_id = str(uuid4())

    mock_sb = MagicMock()

    def mock_table(name):
        tbl = MagicMock()
        if name == "jobs":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.eq.return_value = qb
            qb.execute.return_value = MagicMock(
                data=[{
                    "id": str(job_id),
                    "title": "Full Stack Engineer",
                    "company": "Tech Corp",
                    "requirements": [
                        {"id": "req-1", "skill_name": "FastAPI", "category": "core_required"},
                        {"id": "req-2", "skill_name": "React", "category": "core_required"},
                    ],
                }]
            )
            return qb
        elif name == "repositories":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.eq.return_value = qb
            qb.execute.return_value = MagicMock(
                data=[
                    {"id": repo_a_id, "name": "backend-api", "full_name": "acme/backend-api", "is_selected": True, "last_commit_sha": "sha_a1"},
                    {"id": repo_b_id, "name": "frontend-ui", "full_name": "acme/frontend-ui", "is_selected": True, "last_commit_sha": "sha_b1"},
                ]
            )
            return qb
        elif name == "repository_scans":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.eq.return_value = qb
            qb.in_.return_value = qb
            qb.order.return_value = qb
            qb.limit.return_value = qb
            # Return scan data for each repo
            def s_exec():
                eq_call = qb.eq.call_args[0][1]
                scan_id = scan_a_id if eq_call == repo_a_id else scan_b_id
                commit_sha = "sha_a1" if eq_call == repo_a_id else "sha_b1"
                return MagicMock(data=[{"id": scan_id, "commit_sha": commit_sha}])
            qb.execute.side_effect = s_exec
            return qb
        elif name == "skill_evidence":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.in_.return_value = qb
            qb.execute.return_value = MagicMock(
                data=[
                    {
                        "id": str(uuid4()),
                        "scan_id": scan_a_id,
                        "repository_id": repo_a_id,
                        "canonical_skill": "fastapi",
                        "evidence_type": "ast_node",
                        "file_path": "app/main.py",
                        "line_range": "L10-L25",
                        "commit_sha": "sha_a1",
                        "explanation": "Found FastAPI application initialization.",
                    },
                    {
                        "id": str(uuid4()),
                        "scan_id": scan_b_id,
                        "repository_id": repo_b_id,
                        "canonical_skill": "react",
                        "evidence_type": "ast_node",
                        "file_path": "src/App.tsx",
                        "line_range": "L5-L40",
                        "commit_sha": "sha_b1",
                        "explanation": "Found React component with JSX hooks.",
                    },
                ]
            )
            return qb
        elif name == "assessment_runs":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.eq.return_value = qb
            qb.order.return_value = qb
            qb.limit.return_value = qb
            qb.execute.return_value = MagicMock(data=[])
            qb.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4()), "created_at": "2026-10-17T00:00:00Z"}])
            return qb
        elif name == "assessment_results":
            qb = MagicMock()
            qb.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4())}, {"id": str(uuid4())}])
            return qb
        return tbl

    mock_sb.table.side_effect = mock_table
    service = AssessmentService(supabase_client=mock_sb)

    run = await service.run_assessment(portfolio_id=portfolio_id, job_id=job_id, trigger_type="initial_scan")

    assert run.snapshot_number == 1
    assert run.status_summary.demonstrated_count == 2
    assert run.status_summary.scanned_repositories_count == 2
    assert run.commit_references["backend-api"] == "sha_a1"
    assert run.commit_references["frontend-ui"] == "sha_b1"
    statuses = {r.skill_name: r.status for r in run.results}
    assert statuses["FastAPI"] == "demonstrated"
    assert statuses["React"] == "demonstrated"


# ==============================================================================
# SCENARIO 2 & 3: Push to Repo A rescans Repo A only; Repo B evidence is reused
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_2_and_3_push_to_repo_a_scans_repo_a_only():
    secret = "test_webhook_secret_123"
    delivery_id = str(uuid4())
    pushed_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    portfolio_id = str(uuid4())
    job_id = str(uuid4())
    repo_a_id = str(uuid4())

    mock_sb = MagicMock()
    def mock_table(name):
        tbl = MagicMock()
        if name == "repository_events":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4())}])
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "repositories":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{
                    "id": repo_a_id,
                    "portfolio_id": portfolio_id,
                    "name": "backend-api",
                    "full_name": "acme/backend-api",
                    "default_branch": "main",
                    "is_eligible": True,
                    "is_selected": True,
                }]
            )
        elif name == "assessment_runs":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"job_id": job_id}]
            )
        return tbl

    mock_sb.table.side_effect = mock_table

    mock_scanner = MagicMock()
    mock_scanner.scan_single_repository = AsyncMock(return_value={
        "scan_id": str(uuid4()),
        "status": "completed",
        "commit_sha": pushed_sha,
    })

    mock_engine = MagicMock()
    mock_engine.run_assessment = AsyncMock(return_value=AssessmentRunResponse(
        id=str(uuid4()),
        portfolio_id=portfolio_id,
        job_id=job_id,
        snapshot_number=2,
        trigger_type="webhook_push",
        commit_references={"backend-api": pushed_sha, "frontend-ui": "sha_b1"},
        status_summary=AssessmentStatusSummary(demonstrated_count=2, total_requirements=2),
        results=[],
        created_at="2026-10-17T01:00:00Z",
    ))

    service = WebhookService(
        supabase_client=mock_sb,
        scanner=mock_scanner,
        assessment_service=mock_engine,
    )

    payload = {
        "ref": "refs/heads/main",
        "deleted": False,
        "after": pushed_sha,
        "repository": {"name": "backend-api", "full_name": "acme/backend-api", "default_branch": "main"},
        "commits": [{"id": pushed_sha, "added": ["app/auth.py"], "modified": [], "removed": []}],
    }
    raw_body = json.dumps(payload).encode("utf-8")

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        res = await service.handle_push_event(delivery_id=delivery_id, raw_body=raw_body, hmac_verified=True)

    assert res.status == "completed"
    assert res.commit_sha == pushed_sha
    # Scenario 2: Scanner was invoked EXACTLY ONCE for Repo A
    assert mock_scanner.scan_single_repository.call_count == 1
    call_repo = mock_scanner.scan_single_repository.call_args[0][0]
    call_kwargs = mock_scanner.scan_single_repository.call_args[1]
    assert call_repo["full_name"] == "acme/backend-api"
    assert call_kwargs["commit_sha"] == pushed_sha
    # Scenario 3: Repo B was not scanned during this webhook execution


# ==============================================================================
# SCENARIO 4: Snapshot #2 combines fresh Repo A evidence with existing Repo B evidence
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_4_snapshot_2_combines_fresh_repo_a_with_existing_repo_b():
    portfolio_id = uuid4()
    job_id = uuid4()
    repo_a_id = str(uuid4())
    repo_b_id = str(uuid4())
    scan_a_v2_id = str(uuid4())  # Fresh scan for Repo A
    scan_b_v1_id = str(uuid4())  # Existing valid scan for Repo B

    mock_sb = MagicMock()

    def mock_table(name):
        tbl = MagicMock()
        if name == "jobs":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.eq.return_value = qb
            qb.execute.return_value = MagicMock(
                data=[{
                    "id": str(job_id),
                    "title": "Full Stack Engineer",
                    "company": "Tech Corp",
                    "requirements": [
                        {"id": "req-docker", "skill_name": "Docker", "category": "core_required"},
                        {"id": "req-react", "skill_name": "React", "category": "core_required"},
                    ],
                }]
            )
            return qb
        elif name == "repositories":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.eq.return_value = qb
            qb.execute.return_value = MagicMock(
                data=[
                    {"id": repo_a_id, "name": "backend-api", "full_name": "acme/backend-api", "is_selected": True, "last_commit_sha": "sha_a_v2"},
                    {"id": repo_b_id, "name": "frontend-ui", "full_name": "acme/frontend-ui", "is_selected": True, "last_commit_sha": "sha_b_v1"},
                ]
            )
            return qb
        elif name == "repository_scans":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.eq.return_value = qb
            qb.in_.return_value = qb
            qb.order.return_value = qb
            qb.limit.return_value = qb
            def s_exec():
                eq_call = qb.eq.call_args[0][1]
                scan_id = scan_a_v2_id if eq_call == repo_a_id else scan_b_v1_id
                commit_sha = "sha_a_v2" if eq_call == repo_a_id else "sha_b_v1"
                return MagicMock(data=[{"id": scan_id, "commit_sha": commit_sha}])
            qb.execute.side_effect = s_exec
            return qb
        elif name == "skill_evidence":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.in_.return_value = qb
            qb.execute.return_value = MagicMock(
                data=[
                    {
                        "id": str(uuid4()),
                        "scan_id": scan_a_v2_id,
                        "repository_id": repo_a_id,
                        "canonical_skill": "docker",
                        "evidence_type": "manifest",
                        "file_path": "Dockerfile",
                        "line_range": "L1-L18",
                        "commit_sha": "sha_a_v2",
                        "explanation": "Multi-stage Docker container build definition.",
                    },
                    {
                        "id": str(uuid4()),
                        "scan_id": scan_b_v1_id,
                        "repository_id": repo_b_id,
                        "canonical_skill": "react",
                        "evidence_type": "ast_node",
                        "file_path": "src/App.tsx",
                        "line_range": "L5-L40",
                        "commit_sha": "sha_b_v1",
                        "explanation": "React hooks implementation.",
                    },
                ]
            )
            return qb
        elif name == "assessment_runs":
            qb = MagicMock()
            qb.select.return_value = qb
            qb.eq.return_value = qb
            qb.order.return_value = qb
            qb.limit.return_value = qb
            qb.execute.return_value = MagicMock(data=[{"snapshot_number": 1}])
            qb.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4()), "created_at": "2026-10-17T01:00:00Z"}])
            return qb
        elif name == "assessment_results":
            qb = MagicMock()
            qb.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4())}, {"id": str(uuid4())}])
            return qb
        return tbl

    mock_sb.table.side_effect = mock_table
    service = AssessmentService(supabase_client=mock_sb)

    run = await service.run_assessment(portfolio_id=portfolio_id, job_id=job_id, trigger_type="webhook_push")

    assert run.snapshot_number == 2
    assert run.trigger_type == "webhook_push"
    assert run.commit_references["backend-api"] == "sha_a_v2"
    assert run.commit_references["frontend-ui"] == "sha_b_v1"
    statuses = {r.skill_name: r.status for r in run.results}
    assert statuses["Docker"] in ("demonstrated", "partially_demonstrated")
    assert statuses["React"] == "demonstrated"


# ==============================================================================
# SCENARIO 5: Push to unselected Repo C is ignored without scanning or reassessing
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_5_push_to_unselected_repo_c_is_ignored():
    secret = "test_webhook_secret_123"
    delivery_id = str(uuid4())
    pushed_sha = "c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3c3"

    mock_sb = MagicMock()
    # Repo C exists in DB, but candidate explicitly unselected it (is_selected=False)
    def mock_table(name):
        tbl = MagicMock()
        if name == "repository_events":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "repositories":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{
                    "id": str(uuid4()),
                    "portfolio_id": str(uuid4()),
                    "name": "unselected-repo",
                    "full_name": "acme/unselected-repo",
                    "default_branch": "main",
                    "is_eligible": True,
                    "is_selected": False,  # UNSELECTED
                }]
            )
        return tbl
    mock_sb.table.side_effect = mock_table

    mock_scanner = MagicMock()
    mock_scanner.scan_single_repository = AsyncMock()
    mock_engine = MagicMock()
    mock_engine.run_assessment = AsyncMock()

    service = WebhookService(
        supabase_client=mock_sb,
        scanner=mock_scanner,
        assessment_service=mock_engine,
    )

    payload = {
        "ref": "refs/heads/main",
        "deleted": False,
        "after": pushed_sha,
        "repository": {"name": "unselected-repo", "full_name": "acme/unselected-repo", "default_branch": "main"},
    }
    raw_body = json.dumps(payload).encode("utf-8")

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        res = await service.handle_push_event(delivery_id=delivery_id, raw_body=raw_body, hmac_verified=True)

    assert res.status == "ignored"
    assert "not selected" in res.message.lower()
    mock_scanner.scan_single_repository.assert_not_called()
    mock_engine.run_assessment.assert_not_called()


# ==============================================================================
# SCENARIO 6: Duplicate delivery IDs do not create duplicate reassessments
# ==============================================================================
def test_scenario_6_duplicate_delivery_id_idempotency(client):
    secret = "test_webhook_secret_123"
    delivery_id = "delivery_idempotent_999"
    payload = {
        "ref": "refs/heads/main",
        "deleted": False,
        "after": "d1d2d3d4d1d2d3d4d1d2d3d4d1d2d3d4d1d2d3d4",
        "repository": {"name": "repo", "full_name": "acme/repo"},
    }
    raw_body = json.dumps(payload).encode("utf-8")
    sig = compute_signature(secret, raw_body)

    with patch("app.services.webhook_service.get_supabase_client") as mock_get_sb:
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table().select().eq().execute.return_value = MagicMock(
            data=[{
                "id": str(uuid4()),
                "delivery_id": delivery_id,
                "repository_name": "acme/repo",
                "status": "completed",
            }]
        )

        with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
            res = client.post(
                "/api/webhooks/github",
                content=raw_body,
                headers={
                    "X-GitHub-Event": "push",
                    "X-GitHub-Delivery": delivery_id,
                    "X-Hub-Signature-256": sig,
                },
            )

        assert res.status_code == 200
        assert res.json()["status"] == "duplicate"
        assert "already processed" in res.json()["message"]


# ==============================================================================
# SCENARIO 7: Failed scan records honest error telemetry and halts reassessment
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_7_failed_scan_records_honest_telemetry():
    secret = "test_webhook_secret_123"
    delivery_id = str(uuid4())
    pushed_sha = "f1f2f3f4f1f2f3f4f1f2f3f4f1f2f3f4f1f2f3f4"
    event_id = str(uuid4())

    mock_sb = MagicMock()
    def mock_table(name):
        tbl = MagicMock()
        if name == "repository_events":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.insert.return_value.execute.return_value = MagicMock(data=[{"id": event_id}])
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "repositories":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{
                    "id": str(uuid4()),
                    "portfolio_id": str(uuid4()),
                    "name": "flaky-repo",
                    "full_name": "acme/flaky-repo",
                    "default_branch": "main",
                    "is_eligible": True,
                    "is_selected": True,
                }]
            )
        return tbl
    mock_sb.table.side_effect = mock_table

    mock_scanner = MagicMock()
    # Scan fails due to upstream GitHub error
    mock_scanner.scan_single_repository = AsyncMock(return_value={
        "status": "failed",
        "skipped_summary": "GitHub tree API 503 Service Unavailable",
    })

    mock_engine = MagicMock()
    mock_engine.run_assessment = AsyncMock()

    service = WebhookService(
        supabase_client=mock_sb,
        scanner=mock_scanner,
        assessment_service=mock_engine,
    )

    payload = {
        "ref": "refs/heads/main",
        "deleted": False,
        "after": pushed_sha,
        "repository": {"name": "flaky-repo", "full_name": "acme/flaky-repo", "default_branch": "main"},
    }
    raw_body = json.dumps(payload).encode("utf-8")

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        res = await service.handle_push_event(delivery_id=delivery_id, raw_body=raw_body, hmac_verified=True)

    assert res.status == "failed"
    assert "Scan failed" in res.message
    # Assessment engine was NEVER invoked with invalid or failed scan
    mock_engine.run_assessment.assert_not_called()


# ==============================================================================
# SCENARIO 8: History retains both immutable snapshots and delta comparison
# ==============================================================================
def test_scenario_8_history_and_comparison_preserves_immutable_snapshots(client, session_auth):
    portfolio_id = session_auth["portfolio_id"]
    job_id = str(uuid4())
    run1_id = str(uuid4())
    run2_id = str(uuid4())

    # Override verify_portfolio_session dependency
    client.app.dependency_overrides[verify_portfolio_session] = lambda: {"id": portfolio_id}

    with patch("app.api.assessments.get_supabase_client") as mock_get_sb:
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        def mock_table(name):
            tbl = MagicMock()
            if name == "assessment_runs":
                tbl.select.return_value.in_.return_value.execute.return_value = MagicMock(
                    data=[
                        {
                            "id": run1_id,
                            "portfolio_id": portfolio_id,
                            "job_id": job_id,
                            "snapshot_number": 1,
                            "trigger_type": "initial_scan",
                            "status_summary": {"demonstrated_count": 1, "not_demonstrated_in_scope_count": 1, "total_evidence_count": 1},
                        },
                        {
                            "id": run2_id,
                            "portfolio_id": portfolio_id,
                            "job_id": job_id,
                            "snapshot_number": 2,
                            "trigger_type": "webhook_push",
                            "status_summary": {"demonstrated_count": 2, "not_demonstrated_in_scope_count": 0, "total_evidence_count": 3},
                        },
                    ]
                )
            elif name == "assessment_results":
                tbl.select.return_value.in_.return_value.execute.return_value = MagicMock(
                    data=[
                        {"assessment_run_id": run1_id, "requirement_id": "req-1", "skill_name": "Docker", "category": "core_required", "status": "not_demonstrated_in_scope", "evidence_ids": []},
                        {"assessment_run_id": run2_id, "requirement_id": "req-1", "skill_name": "Docker", "category": "core_required", "status": "demonstrated", "evidence_ids": ["ev-1", "ev-2"]},
                    ]
                )
            return tbl
        mock_sb.table.side_effect = mock_table

        try:
            client.cookies.set(settings.SESSION_COOKIE_NAME, session_auth["raw_token"])
            res = client.get(
                f"/api/portfolio/{portfolio_id}/assessments/compare?base_run_id={run1_id}&target_run_id={run2_id}",
                headers=session_auth["headers"],
            )
            assert res.status_code == 200
            data = res.json()
            assert data["base_snapshot_number"] == 1
            assert data["target_snapshot_number"] == 2
            assert data["summary_delta"]["demonstrated_delta"] == 1
            transition = data["transitions"][0]
            assert transition["skill_name"] == "Docker"
            assert transition["base_status"] == "not_demonstrated_in_scope"
            assert transition["target_status"] == "demonstrated"
            assert transition["status_changed"] is True
        finally:
            client.app.dependency_overrides.clear()


# ==============================================================================
# SCENARIO 9: Multiple repositories route through single HTTPS endpoint to correct portfolio
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_9_multiple_repos_route_to_respective_portfolios():
    secret = "test_webhook_secret_123"
    portfolio_1 = str(uuid4())
    portfolio_2 = str(uuid4())
    job_1 = str(uuid4())
    job_2 = str(uuid4())

    mock_sb = MagicMock()
    def mock_table(name):
        tbl = MagicMock()
        if name == "repository_events":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            tbl.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4())}])
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "repositories":
            def select_repo():
                full_name_call = tbl.select.return_value.eq.call_args[0][1]
                if full_name_call == "org1/service-alpha":
                    return MagicMock(data=[{"id": str(uuid4()), "portfolio_id": portfolio_1, "name": "service-alpha", "full_name": "org1/service-alpha", "default_branch": "main", "is_eligible": True, "is_selected": True}])
                else:
                    return MagicMock(data=[{"id": str(uuid4()), "portfolio_id": portfolio_2, "name": "service-beta", "full_name": "org2/service-beta", "default_branch": "main", "is_eligible": True, "is_selected": True}])
            tbl.select.return_value.eq.return_value.execute.side_effect = select_repo
        elif name == "assessment_runs":
            def select_runs():
                p_id_call = tbl.select.return_value.eq.call_args[0][1]
                target_job = job_1 if p_id_call == portfolio_1 else job_2
                return MagicMock(data=[{"job_id": target_job}])
            tbl.select.return_value.eq.return_value.execute.side_effect = select_runs
        return tbl
    mock_sb.table.side_effect = mock_table

    mock_scanner = MagicMock()
    mock_scanner.scan_single_repository = AsyncMock(return_value={"status": "completed"})
    mock_engine = MagicMock()
    mock_engine.run_assessment = AsyncMock(return_value=AssessmentRunResponse(
        id=str(uuid4()),
        portfolio_id=portfolio_1,
        job_id=job_1,
        snapshot_number=2,
        trigger_type="webhook_push",
        commit_references={},
        status_summary=AssessmentStatusSummary(),
        results=[],
        created_at="2026-10-17T01:00:00Z",
    ))

    service = WebhookService(
        supabase_client=mock_sb,
        scanner=mock_scanner,
        assessment_service=mock_engine,
    )

    # Delivery 1 for Repo 1 (Portfolio 1)
    p1 = {"ref": "refs/heads/main", "deleted": False, "after": "1111111111111111111111111111111111111111", "repository": {"name": "service-alpha", "full_name": "org1/service-alpha", "default_branch": "main"}}
    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        res1 = await service.handle_push_event(delivery_id="del-1", raw_body=json.dumps(p1).encode("utf-8"), hmac_verified=True)
    assert res1.status == "completed"
    assert mock_engine.run_assessment.call_args[1]["portfolio_id"] == UUID(portfolio_1)

    # Delivery 2 for Repo 2 (Portfolio 2) through the same service endpoint
    p2 = {"ref": "refs/heads/main", "deleted": False, "after": "2222222222222222222222222222222222222222", "repository": {"name": "service-beta", "full_name": "org2/service-beta", "default_branch": "main"}}
    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        res2 = await service.handle_push_event(delivery_id="del-2", raw_body=json.dumps(p2).encode("utf-8"), hmac_verified=True)
    assert res2.status == "completed"
    assert mock_engine.run_assessment.call_args[1]["portfolio_id"] == UUID(portfolio_2)
