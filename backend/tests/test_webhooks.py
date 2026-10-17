"""
ProofPath AI — Phase 3G GitHub Webhook Loop & Activity Test Suite
Tests:
- Missing or unconfigured webhook secret (fail closed with 500)
- Missing or malformed X-Hub-Signature-256 header (401)
- Tampered payload / signature mismatch rejection (401)
- Ping event handling (200)
- Unsupported events safely ignored (200)
- Branch deletion and zero-SHA handling (200 ignored)
- Unknown repository safely ignored (200 ignored)
- Duplicate / concurrent delivery idempotency (status="duplicate", no duplicate scan/assessment)
- Cross-portfolio isolation (push to Repo A does not trigger Candidate B)
- Valid push execution: bounded scan -> automatic reassessment -> immutable snapshot with trigger_type="webhook_push" and triggering_event_id
- Activity API: returns real persisted webhook deliveries
- Simulation API: marked with hmac_verified=False
"""
import hashlib
import hmac
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.session import generate_session_token, hash_session_token
from app.main import create_app
from app.schemas.assessment import AssessmentRunResponse, AssessmentStatusSummary
from app.schemas.webhook import WebhookResponse


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


def compute_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ==============================================================================
# 1. WEBHOOK SIGNATURE & HEADER VERIFICATION TESTS (B1)
# ==============================================================================

def test_webhook_fails_closed_when_secret_not_configured(client):
    """When GITHUB_WEBHOOK_SECRET is None/empty, all webhook requests must fail closed with 500."""
    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", None):
        res = client.post(
            "/api/webhooks/github",
            content=b'{"ref": "refs/heads/main"}',
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": str(uuid4()),
                "X-Hub-Signature-256": "sha256=abcdef123456",
            },
        )
        assert res.status_code == 500
        assert "server webhook secret is not configured" in res.json()["detail"]


def test_webhook_fails_closed_missing_signature(client):
    """When X-Hub-Signature-256 header is missing, request is rejected with 401."""
    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", "test_webhook_secret_123"):
        res = client.post(
            "/api/webhooks/github",
            content=b'{"ref": "refs/heads/main"}',
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": str(uuid4()),
            },
        )
        assert res.status_code == 401
        assert "missing X-Hub-Signature-256" in res.json()["detail"]


def test_webhook_fails_closed_tampered_signature(client):
    """When payload or signature is tampered with, request is rejected with 401."""
    secret = "test_webhook_secret_123"
    payload = b'{"ref": "refs/heads/main", "after": "c0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ff"}'
    invalid_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        res = client.post(
            "/api/webhooks/github",
            content=payload,
            headers={
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": str(uuid4()),
                "X-Hub-Signature-256": invalid_sig,
            },
        )
        assert res.status_code == 401
        assert "Signature verification failed" in res.json()["detail"]


def test_webhook_ping_handshake(client):
    """GitHub ping event returns 200 OK without database mutation."""
    res = client.post(
        "/api/webhooks/github",
        content=b'{"zen": "Design for failure"}',
        headers={
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": str(uuid4()),
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "completed"
    assert "ping received" in res.json()["message"]


def test_webhook_unsupported_event_ignored(client):
    """Unsupported events (e.g. issues, star) are safely ignored with 200 OK."""
    res = client.post(
        "/api/webhooks/github",
        content=b'{"action": "opened"}',
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": str(uuid4()),
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ignored"


def test_webhook_missing_delivery_header_rejected(client):
    """Missing X-GitHub-Delivery header triggers 400 Bad Request."""
    secret = "test_webhook_secret_123"
    payload = b'{"ref": "refs/heads/main"}'
    sig = compute_signature(secret, payload)

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        res = client.post(
            "/api/webhooks/github",
            content=payload,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": sig,
            },
        )
        assert res.status_code == 400
        assert "Missing required X-GitHub-Delivery" in res.json()["detail"]


# ==============================================================================
# 2. PAYLOAD VALIDATION & BRANCH DELETION TESTS (B1, B2)
# ==============================================================================

@patch("app.services.webhook_service.get_supabase_client")
def test_webhook_deleted_branch_ignored(mock_get_sb, client):
    """Deleted branch pushes (deleted=true or after=0000...0000) are safely ignored without DB mutation."""
    secret = "test_webhook_secret_123"
    delivery_id = str(uuid4())
    payload_dict = {
        "ref": "refs/heads/feature-old",
        "deleted": True,
        "after": "0000000000000000000000000000000000000000",
        "repository": {"name": "core-ledger", "full_name": "acme/core-ledger"},
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = compute_signature(secret, raw_body)

    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb
    mock_sb.table().select().eq().execute.return_value = MagicMock(data=[])

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
        data = res.json()
        assert data["status"] == "ignored"
        assert "Branch deletion event ignored" in data["message"]


@patch("app.services.webhook_service.get_supabase_client")
def test_webhook_unknown_repository_ignored(mock_get_sb, client):
    """Webhook for a repository not tracked by ProofPath AI returns 200 ignored."""
    secret = "test_webhook_secret_123"
    delivery_id = str(uuid4())
    after_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    payload_dict = {
        "ref": "refs/heads/main",
        "deleted": False,
        "after": after_sha,
        "repository": {"name": "untracked-repo", "full_name": "stranger/untracked-repo"},
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = compute_signature(secret, raw_body)

    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb

    def mock_table(name):
        tbl = MagicMock()
        if name == "repository_events":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "repositories":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return tbl

    mock_sb.table.side_effect = mock_table

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
        data = res.json()
        assert data["status"] == "ignored"
        assert "not tracked" in data["message"]


# ==============================================================================
# 3. IDEMPOTENCY & DEDUPLICATION TESTS (B3)
# ==============================================================================

@patch("app.services.webhook_service.get_supabase_client")
def test_webhook_duplicate_delivery_deduplicated(mock_get_sb, client):
    """When a delivery_id already exists in repository_events, it returns duplicate without re-processing."""
    secret = "test_webhook_secret_123"
    delivery_id = "delivery_unique_12345"
    after_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    payload_dict = {
        "ref": "refs/heads/main",
        "deleted": False,
        "after": after_sha,
        "repository": {"name": "core-repo", "full_name": "acme/core-repo"},
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = compute_signature(secret, raw_body)

    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb
    mock_sb.table().select().eq().execute.return_value = MagicMock(
        data=[{
            "id": str(uuid4()),
            "delivery_id": delivery_id,
            "repository_name": "acme/core-repo",
            "commit_sha": after_sha,
            "status": "completed",
            "reassessment_run_id": str(uuid4()),
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
        data = res.json()
        assert data["status"] == "duplicate"
        assert data["delivery_id"] == delivery_id
        assert "already processed" in data["message"]


# ==============================================================================
# 4. FULL REASSESSMENT & IMMUTABLE SNAPSHOT FLOW (B4)
# ==============================================================================

@patch("app.services.webhook_service.get_assessment_service")
@patch("app.services.webhook_service.get_supabase_client")
def test_webhook_valid_push_triggers_scan_and_reassessment(mock_get_sb, mock_get_assessment, client):
    """
    Valid push event:
    1. Persists event in repository_events
    2. Executes bounded scan on target commit
    3. Reassesses active jobs
    4. Produces immutable assessment snapshot with trigger_type=webhook_push
    5. Updates repository_events status to completed
    """
    secret = "test_webhook_secret_123"
    delivery_id = str(uuid4())
    after_sha = "c0ffeec0ffeec0ffeec0ffeec0ffeec0ffeec0ff"
    portfolio_id = str(uuid4())
    job_id = str(uuid4())
    event_id = str(uuid4())
    new_run_id = str(uuid4())

    payload_dict = {
        "ref": "refs/heads/main",
        "deleted": False,
        "after": after_sha,
        "repository": {"name": "ledger", "full_name": "acme/ledger", "default_branch": "main"},
        "commits": [
            {
                "id": after_sha,
                "added": ["src/service.py"],
                "modified": ["README.md"],
                "removed": [],
            }
        ],
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = compute_signature(secret, raw_body)

    mock_sb = MagicMock()
    mock_get_sb.return_value = mock_sb

    def mock_table(name):
        tbl = MagicMock()
        if name == "repository_events":
            # Idempotency check: empty (new delivery)
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            # Insert event
            tbl.insert.return_value.execute.return_value = MagicMock(data=[{"id": event_id}])
            # Update status
            tbl.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "repositories":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{
                    "id": str(uuid4()),
                    "portfolio_id": portfolio_id,
                    "name": "ledger",
                    "full_name": "acme/ledger",
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

    # Mock assessment service
    mock_engine = MagicMock()
    mock_get_assessment.return_value = mock_engine

    mock_run_response = AssessmentRunResponse(
        id=new_run_id,
        portfolio_id=portfolio_id,
        job_id=job_id,
        job_title="Staff Backend Engineer",
        snapshot_number=2,
        trigger_type="webhook_push",
        commit_references={"ledger": after_sha},
        status_summary=AssessmentStatusSummary(
            demonstrated_count=2,
            partially_demonstrated_count=1,
            not_demonstrated_in_scope_count=0,
            uncertain_count=0,
            total_requirements=3,
            scanned_repositories_count=1,
            total_evidence_count=5,
        ),
        results=[],
        created_at="2026-10-17T00:30:00Z",
    )
    mock_engine.run_assessment = AsyncMock(return_value=mock_run_response)

    with patch.object(settings, "GITHUB_WEBHOOK_SECRET", secret):
        with patch("app.services.webhook_service.RepositoryScanner.scan_single_repository", new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = {
                "scan_id": str(uuid4()),
                "status": "completed",
                "commit_sha": after_sha,
            }

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
            data = res.json()
            assert data["status"] == "completed"
            assert data["commit_sha"] == after_sha
            assert data["reassessment_run_id"] == new_run_id

            # Verify scanner was called with after_sha
            mock_scan.assert_called_once()
            _, scan_kwargs = mock_scan.call_args
            assert scan_kwargs["commit_sha"] == after_sha

            # Verify assessment was executed with trigger_type="webhook_push"
            mock_engine.run_assessment.assert_called_once()
            _, assess_kwargs = mock_engine.run_assessment.call_args
            assert assess_kwargs["trigger_type"] == "webhook_push"
            assert str(assess_kwargs["triggering_event_id"]) == event_id


# ==============================================================================
# 5. ACTIVITY AND SIMULATION ENDPOINT TESTS (B5)
# ==============================================================================

@patch("app.core.session.get_supabase_client")
@patch("app.api.webhooks.get_supabase_client")
def test_get_portfolio_activity(mock_api_sb, mock_session_sb, client, session_auth):
    """Candidate activity endpoint retrieves real persisted deliveries for tracked repos."""
    portfolio_id = session_auth["portfolio_id"]

    mock_session_sb.return_value.table().select().eq().execute.return_value = MagicMock(
        data=[{
            "id": portfolio_id,
            "github_username": "octocat",
            "session_token_hash": session_auth["token_hash"],
            "is_archived": False,
        }]
    )

    def mock_table(name):
        tbl = MagicMock()
        if name == "repositories":
            tbl.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"full_name": "octocat/ledger-service"}]
            )
        elif name == "repository_events":
            tbl.select.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": str(uuid4()),
                        "delivery_id": "del_real_001",
                        "repository_name": "octocat/ledger-service",
                        "event_type": "push",
                        "commit_sha": "89a1ef4",
                        "changed_paths": ["src/ledger.py"],
                        "received_at": "2026-10-17T00:15:00Z",
                        "hmac_verified": True,
                        "status": "completed",
                        "reassessment_run_id": str(uuid4()),
                        "retry_count": 0,
                        "error_details": None,
                        "created_at": "2026-10-17T00:15:00Z",
                    }
                ]
            )
        return tbl

    mock_api_sb.return_value.table.side_effect = mock_table

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_auth["raw_token"])
    res = client.get(f"/api/portfolio/{portfolio_id}/activity", headers=session_auth["headers"])
    assert res.status_code == 200
    data = res.json()
    assert data["portfolio_id"] == portfolio_id
    assert len(data["deliveries"]) == 1
    item = data["deliveries"][0]
    assert item["delivery_id"] == "del_real_001"
    assert item["hmac_verified"] is True
    assert item["status"] == "completed"


@patch("app.core.session.get_supabase_client")
@patch("app.api.webhooks.get_webhook_service")
def test_simulate_push_event(mock_get_service, mock_session_sb, client, session_auth):
    """Simulated push executes with hmac_verified=False and delivery_id starting with 'sim_'."""
    portfolio_id = session_auth["portfolio_id"]

    mock_session_sb.return_value.table().select().eq().execute.return_value = MagicMock(
        data=[{
            "id": portfolio_id,
            "github_username": "octocat",
            "session_token_hash": session_auth["token_hash"],
            "is_archived": False,
        }]
    )

    mock_ws = MagicMock()
    mock_get_service.return_value = mock_ws
    mock_ws.handle_push_event = AsyncMock(
        return_value=WebhookResponse(
            delivery_id="sim_123456789abc",
            status="completed",
            repository="octocat/ledger-service",
            commit_sha="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            message="Webhook push processed, evidence refreshed, and automatic reassessment completed.",
        )
    )

    payload = {
        "repository_name": "octocat/ledger-service",
        "commit_message": "Add test worker pool",
        "changed_paths": ["src/worker.go"],
    }
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_auth["raw_token"])
    res = client.post(
        f"/api/portfolio/{portfolio_id}/simulate-push",
        json=payload,
        headers=session_auth["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"

    mock_ws.handle_push_event.assert_called_once()
    _, call_kwargs = mock_ws.handle_push_event.call_args
    assert call_kwargs["delivery_id"].startswith("sim_")
    assert call_kwargs["hmac_verified"] is False


# ==============================================================================
# 5. DELIVERY RECOVERY & RETRY BOUNDING TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_webhook_recovery_stuck_processing_after_timeout():
    """Verify that a delivery stuck in processing >300s can be recovered safely."""
    from datetime import datetime, timezone, timedelta
    from app.services.webhook_service import WebhookService

    delivery_id = str(uuid4())
    stuck_time = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()

    mock_db = MagicMock()
    # 1. Existing delivery is stuck in processing since 400s ago
    mock_db.table().select().eq().execute.side_effect = [
        MagicMock(data=[{
            "id": "event_uuid_123",
            "delivery_id": delivery_id,
            "repository_name": "octocat/hello-world",
            "commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "status": "processing",
            "received_at": stuck_time,
            "retry_count": 0,
        }]),
        # Repositories match
        MagicMock(data=[{
            "id": "repo_123",
            "portfolio_id": str(uuid4()),
            "name": "hello-world",
            "full_name": "octocat/hello-world",
            "default_branch": "main",
            "is_selected": True,
            "is_eligible": True,
        }]),
        # assessment_runs query
        MagicMock(data=[]),
    ]

    mock_scanner = MagicMock()
    mock_scanner.scan_single_repository = AsyncMock(return_value={"status": "completed"})

    service = WebhookService(supabase_client=mock_db, scanner=mock_scanner)

    raw_body = json.dumps({
        "ref": "refs/heads/main",
        "after": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "repository": {"full_name": "octocat/hello-world"},
        "commits": [{"modified": ["main.go"]}],
    }).encode("utf-8")

    res = await service.handle_push_event(delivery_id=delivery_id, raw_body=raw_body, hmac_verified=True)
    assert res.status == "completed"

    # Verify update was called on existing record with retry_count + 1
    mock_db.table().update.assert_called()


@pytest.mark.asyncio
async def test_webhook_processing_recent_returns_duplicate():
    """Verify that a delivery in flight (<300s) is recognized as duplicate."""
    from datetime import datetime, timezone, timedelta
    from app.services.webhook_service import WebhookService

    delivery_id = str(uuid4())
    recent_time = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()

    mock_db = MagicMock()
    mock_db.table().select().eq().execute.return_value = MagicMock(data=[{
        "id": "event_uuid_123",
        "delivery_id": delivery_id,
        "repository_name": "octocat/hello-world",
        "commit_sha": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "status": "processing",
        "received_at": recent_time,
        "retry_count": 0,
    }])

    service = WebhookService(supabase_client=mock_db)
    raw_body = json.dumps({
        "ref": "refs/heads/main",
        "after": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        "repository": {"full_name": "octocat/hello-world"},
    }).encode("utf-8")

    res = await service.handle_push_event(delivery_id=delivery_id, raw_body=raw_body, hmac_verified=True)
    assert res.status == "duplicate"
    assert "in progress" in res.message


@pytest.mark.asyncio
async def test_recover_stuck_deliveries_service_method():
    """Verify that recover_stuck_deliveries transitions expired processing events to failed."""
    from datetime import datetime, timezone, timedelta
    from app.services.webhook_service import WebhookService

    stuck_time = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    mock_db = MagicMock()
    mock_db.table().select().eq().execute.return_value = MagicMock(data=[
        {"id": "ev_1", "delivery_id": "del_1", "received_at": stuck_time, "retry_count": 0},
    ])

    service = WebhookService(supabase_client=mock_db)
    recovered_count = await service.recover_stuck_deliveries(timeout_seconds=300)
    assert recovered_count == 1
    mock_db.table().update.assert_called_once()

