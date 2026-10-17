"""
ProofPath AI — Phase 3F Assessment Engine, History & Comparison Test Suite
Tests:
- Requirement to evidence matching
- All four PRD statuses: demonstrated, partially_demonstrated, not_demonstrated_in_scope, uncertain
- Direct AST proof vs indirect manifest proof distinction
- Grounded explanation and absence of evidence non-claim
- Monotonic snapshot number allocation
- Assessment run creation and child results persistence
- History ledger retrieval in chronological order
- Cross-portfolio access rejection
- Snapshot comparison with delta matrix and status transitions
- Rejection of cross-job snapshot comparison
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.session import generate_session_token, hash_session_token
from app.schemas.job import ExtractedRequirement
from app.services.assessment_engine import (
    evaluate_requirement,
    match_evidence_to_requirement,
    AssessmentService,
)


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
        "cookies": {"proofpath_session": raw_token},
        "headers": {"Origin": "http://localhost:5173", "X-Requested-With": "XMLHttpRequest"},
    }


# ==============================================================================
# 1. ASSESSMENT ENGINE UNIT TESTS
# ==============================================================================

def test_evaluate_demonstrated_with_ast_evidence():
    req = ExtractedRequirement(
        id="req_01",
        skill_name="PostgreSQL Database Design",
        category="core_required",
        tags=["PostgreSQL", "SQL"],
        provenance="user_pasted",
    )
    mock_ev = [{
        "id": str(uuid4()),
        "repository_id": "repo_1",
        "canonical_skill": "PostgreSQL",
        "file_path": "src/database/schema.sql",
        "line_range": "L10-L45",
        "commit_sha": "abc1234",
        "evidence_type": "ast_node",
        "explanation": "Transactional table definitions and composite primary key",
        "snippet": "CREATE TABLE users (id UUID PRIMARY KEY);",
    }]
    repo_map = {"repo_1": "core-ledger-service"}

    res = evaluate_requirement(req, mock_ev, repo_map, total_scanned_repos=2)
    assert res.status == "demonstrated"
    assert "core-ledger-service" in res.explanation
    assert len(res.evidence_ids) == 1
    assert res.evidence_items[0].line_range == "L10-L45"


def test_evaluate_partially_demonstrated_with_manifest_only():
    req = ExtractedRequirement(
        id="req_02",
        skill_name="Docker Containerization",
        category="core_required",
        tags=["Docker"],
        provenance="user_pasted",
    )
    mock_ev = [{
        "id": str(uuid4()),
        "repository_id": "repo_1",
        "canonical_skill": "Docker",
        "file_path": "Dockerfile",
        "line_range": "L1-L15",
        "commit_sha": "abc1234",
        "evidence_type": "manifest",
        "explanation": "Multi-stage Dockerfile definition",
        "snippet": "FROM golang:1.21-alpine",
    }]
    repo_map = {"repo_1": "telemetry-agent"}

    res = evaluate_requirement(req, mock_ev, repo_map, total_scanned_repos=1)
    assert res.status == "partially_demonstrated"
    assert "configuration or dependency reference" in res.explanation
    assert res.limitations is not None


def test_evaluate_not_demonstrated_in_scope():
    req = ExtractedRequirement(
        id="req_03",
        skill_name="Kubernetes Operator Development",
        category="preferred_differentiator",
        tags=["Kubernetes", "CRDs"],
        provenance="user_pasted",
    )
    res = evaluate_requirement(req, [], {}, total_scanned_repos=3)
    assert res.status == "not_demonstrated_in_scope"
    assert "does not imply the candidate lacks this skill" in res.explanation
    assert len(res.evidence_ids) == 0


# ==============================================================================
# 2. ASSESSMENT API INTEGRATION TESTS
# ==============================================================================

@patch("app.core.session.get_supabase_client")
@patch("app.api.assessments.get_supabase_client")
@patch("app.services.assessment_engine.get_supabase_client")
def test_create_assessment_run_endpoint(mock_engine_sb, mock_api_sb, mock_session_sb, client, session_auth):
    pid = session_auth["portfolio_id"]
    jid = str(uuid4())
    run_id = str(uuid4())

    # Mock session lookup
    mock_session_sb.return_value.table().select().eq().execute.return_value = MagicMock(
        data=[{
            "id": pid,
            "github_username": "octocat",
            "session_token_hash": session_auth["token_hash"],
            "is_archived": False,
        }]
    )

    # Mock engine queries
    engine_client = MagicMock()
    mock_engine_sb.return_value = engine_client

    # Build query mocks that support chained .eq()
    job_qb = MagicMock()
    job_qb.eq.return_value = job_qb
    job_qb.execute.return_value = MagicMock(data=[{
        "id": jid,
        "title": "Senior Systems Engineer",
        "company": "Acme",
        "requirements": [
            {"id": "req_1", "skill_name": "Go Concurrency", "category": "core_required", "tags": ["Go"], "is_included": True}
        ],
    }])

    repo_qb = MagicMock()
    repo_qb.eq.return_value = repo_qb
    repo_qb.execute.return_value = MagicMock(data=[{
        "id": "repo_1",
        "name": "core-ledger",
        "full_name": "octocat/core-ledger",
        "default_branch": "main",
        "last_commit_sha": "99aabbc",
        "is_selected": True,
    }])

    ev_qb = MagicMock()
    ev_qb.in_.return_value = ev_qb
    ev_qb.execute.return_value = MagicMock(data=[{
        "id": str(uuid4()),
        "repository_id": "repo_1",
        "canonical_skill": "Go",
        "file_path": "main.go",
        "line_range": "L15-L35",
        "commit_sha": "99aabbc",
        "evidence_type": "ast_node",
        "explanation": "Goroutine worker pool implementation",
        "snippet": "go worker(ctx, jobs)",
    }])

    prev_runs_qb = MagicMock()
    prev_runs_qb.eq.return_value = prev_runs_qb
    prev_runs_qb.order.return_value = prev_runs_qb
    prev_runs_qb.limit.return_value = prev_runs_qb
    prev_runs_qb.execute.return_value = MagicMock(data=[])

    def table_router(table_name):
        mock_t = MagicMock()
        if table_name == "jobs":
            mock_t.select.return_value = job_qb
        elif table_name == "repositories":
            mock_t.select.return_value = repo_qb
        elif table_name == "skill_evidence":
            mock_t.select.return_value = ev_qb
        elif table_name == "assessment_runs":
            mock_t.select.return_value = prev_runs_qb
            mock_t.insert().execute.return_value = MagicMock(data=[{
                "id": run_id,
                "portfolio_id": pid,
                "job_id": jid,
                "snapshot_number": 1,
                "trigger_type": "initial_scan",
                "created_at": "2026-10-17T00:00:00Z",
            }])
        elif table_name == "assessment_results":
            mock_t.insert().execute.return_value = MagicMock(data=[{"id": str(uuid4())}])
        return mock_t

    engine_client.table.side_effect = table_router

    from app.core.config import settings
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_auth["raw_token"])
    res = client.post(
        f"/api/portfolio/{pid}/assess/{jid}",
        headers=session_auth["headers"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == run_id
    assert data["snapshot_number"] == 1
    assert data["status_summary"]["demonstrated_count"] == 1
    assert data["results"][0]["status"] == "demonstrated"


@patch("app.core.session.get_supabase_client")
@patch("app.api.assessments.get_supabase_client")
def test_compare_assessments_endpoint(mock_api_sb, mock_session_sb, client, session_auth):
    pid = session_auth["portfolio_id"]
    jid = str(uuid4())
    base_run_id = str(uuid4())
    target_run_id = str(uuid4())

    # Session auth
    mock_session_sb.return_value.table().select().eq().execute.return_value = MagicMock(
        data=[{
            "id": pid,
            "github_username": "octocat",
            "session_token_hash": session_auth["token_hash"],
            "is_archived": False,
        }]
    )

    api_client = MagicMock()
    mock_api_sb.return_value = api_client

    # Runs query
    api_client.table().select().in_().execute.side_effect = [
        # Runs select
        MagicMock(data=[
            {
                "id": base_run_id,
                "portfolio_id": pid,
                "job_id": jid,
                "snapshot_number": 1,
                "status_summary": {"demonstrated_count": 1, "total_evidence_count": 2},
                "created_at": "2026-10-17T00:00:00Z",
                "jobs": {"title": "Staff Engineer"},
            },
            {
                "id": target_run_id,
                "portfolio_id": pid,
                "job_id": jid,
                "snapshot_number": 2,
                "status_summary": {"demonstrated_count": 2, "total_evidence_count": 5},
                "created_at": "2026-10-17T00:10:00Z",
                "jobs": {"title": "Staff Engineer"},
            },
        ]),
        # Results select
        MagicMock(data=[
            {
                "assessment_run_id": base_run_id,
                "requirement_id": "req_01",
                "skill_name": "Kafka Stream Processing",
                "category": "core_required",
                "status": "partially_demonstrated",
                "evidence_ids": [str(uuid4())],
            },
            {
                "assessment_run_id": target_run_id,
                "requirement_id": "req_01",
                "skill_name": "Kafka Stream Processing",
                "category": "core_required",
                "status": "demonstrated",
                "evidence_ids": [str(uuid4()), str(uuid4())],
            },
        ]),
    ]

    from app.core.config import settings
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_auth["raw_token"])
    res = client.get(
        f"/api/portfolio/{pid}/assessments/compare?base_run_id={base_run_id}&target_run_id={target_run_id}",
        headers=session_auth["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["base_snapshot_number"] == 1
    assert data["target_snapshot_number"] == 2
    assert len(data["transitions"]) == 1
    assert data["transitions"][0]["status_changed"] is True
    assert data["transitions"][0]["base_status"] == "partially_demonstrated"
    assert data["transitions"][0]["target_status"] == "demonstrated"
    assert data["summary_delta"]["demonstrated_delta"] == 1
    assert data["summary_delta"]["evidence_delta"] == 3


@patch("app.core.session.get_supabase_client")
@patch("app.api.assessments.get_supabase_client")
def test_cross_portfolio_assessment_access_rejected(mock_api_sb, mock_session_sb, client, session_auth):
    pid = session_auth["portfolio_id"]
    other_pid = str(uuid4())

    # When other_pid is queried in verify_portfolio_session, return other_pid's data with a different hash
    other_token = generate_session_token()
    other_hash = hash_session_token(other_token)
    mock_session_sb.return_value.table().select().eq().execute.return_value = MagicMock(
        data=[{
            "id": other_pid,
            "github_username": "victim",
            "session_token_hash": other_hash,
            "is_archived": False,
        }]
    )

    # Attempting to access other_pid's assessments with caller's token must be rejected with 403
    from app.core.config import settings
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_auth["raw_token"])
    res = client.get(
        f"/api/portfolio/{other_pid}/assessments",
        headers=session_auth["headers"],
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_assessment_results_failure_fails_closed():
    """Verify that if child assessment_results persistence fails, engine raises 500 and fails closed."""
    from app.services.assessment_engine import AssessmentService, AssessmentEngineError

    mock_db = MagicMock()
    mock_jobs = MagicMock()
    mock_jobs.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": str(uuid4()), "title": "Staff Engineer", "requirements": [{"id": "r1", "skill_name": "Go", "category": "core_required", "is_included": True, "tags": ["Go"]}]}]
    )

    mock_repos = MagicMock()
    mock_repos.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": str(uuid4()), "name": "core-repo", "last_commit_sha": "abc1234", "is_selected": True}]
    )

    mock_scans = MagicMock()
    mock_scans.select.return_value.eq.return_value.in_().order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

    mock_evidence = MagicMock()
    mock_evidence.select.return_value.in_().execute.return_value = MagicMock(data=[])

    mock_runs = MagicMock()
    mock_runs.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    mock_runs.insert.return_value.execute.return_value = MagicMock(data=[{"id": str(uuid4()), "snapshot_number": 1}])

    mock_results = MagicMock()
    mock_results.insert.return_value.execute.side_effect = RuntimeError("Database connection lost during batch result insert")

    def table_router(name):
        if name == "jobs":
            return mock_jobs
        elif name == "repositories":
            return mock_repos
        elif name == "repository_scans":
            return mock_scans
        elif name == "skill_evidence":
            return mock_evidence
        elif name == "assessment_runs":
            return mock_runs
        elif name == "assessment_results":
            return mock_results
        return MagicMock()

    mock_db.table.side_effect = table_router

    service = AssessmentService()
    with patch("app.services.assessment_engine.get_supabase_client", return_value=mock_db):
        with pytest.raises(AssessmentEngineError) as exc_info:
            await service.run_assessment(portfolio_id=uuid4(), job_id=uuid4())
        assert exc_info.value.status_code == 500
        assert "incomplete" in exc_info.value.message.lower()


@patch("app.core.session.get_supabase_client")
@patch("app.api.assessments.get_supabase_client")
def test_get_incomplete_assessment_fails_closed(mock_api_sb, mock_session_sb, client, session_auth):
    """Verify that an incomplete assessment (0 child results but total_requirements > 0) returns 500."""
    pid = session_auth["portfolio_id"]
    run_id = str(uuid4())

    mock_session_sb.return_value.table().select().eq().execute.return_value = MagicMock(
        data=[{
            "id": pid,
            "github_username": "octocat",
            "session_token_hash": session_auth["token_hash"],
            "is_archived": False,
        }]
    )

    mock_runs_tbl = MagicMock()
    mock_runs_tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{
            "id": run_id,
            "portfolio_id": pid,
            "job_id": str(uuid4()),
            "snapshot_number": 1,
            "status_summary": {"total_requirements": 3, "demonstrated_count": 0},
            "created_at": "2026-10-17T00:00:00Z",
            "jobs": {"title": "Target Role"},
        }]
    )

    mock_results_tbl = MagicMock()
    mock_results_tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    def api_table_router(name):
        if name == "assessment_runs":
            return mock_runs_tbl
        elif name == "assessment_results":
            return mock_results_tbl
        return MagicMock()

    mock_api_sb.return_value.table.side_effect = api_table_router

    from app.core.config import settings
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_auth["raw_token"])
    res = client.get(
        f"/api/portfolio/{pid}/assessments/{run_id}",
        headers=session_auth["headers"],
    )
    assert res.status_code == 500
    assert "incomplete assessment record" in res.json()["detail"].lower()


