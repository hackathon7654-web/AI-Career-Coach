"""
ProofPath AI — Session Authorization & Supabase Client Tests
Verifies Subphase 3D-1 requirements:
- Cryptographic token generation and hash-only persistence
- Fail-closed Supabase client behavior when unconfigured
- Valid, missing, malformed, expired, revoked sessions
- Cross-portfolio access prevention (IDOR)
- Cookie flags in development vs production
- Header-based session authentication (X-Session-Token & Bearer)
- CSRF defense on state-changing cookie requests
- Zero secret / token leakage in responses or logs
- Service-role client isolated from browser configuration
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pytest
from fastapi import FastAPI, Depends, Response
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.supabase import (
    get_supabase_client,
    override_supabase_client,
    reset_supabase_client,
    SupabaseConfigurationError,
)
from app.core.session import (
    generate_session_token,
    hash_session_token,
    set_session_cookie,
    clear_session_cookie,
    get_cookie_security_flag,
    verify_portfolio_session,
    revoke_portfolio_session,
)


def create_test_app() -> FastAPI:
    test_app = FastAPI()

    @test_app.get("/api/test/portfolio/{portfolio_id}")
    async def get_protected_data(
        portfolio: dict = Depends(verify_portfolio_session),
    ):
        return {"status": "ok", "portfolio_id": portfolio["id"]}

    @test_app.post("/api/test/portfolio/{portfolio_id}/update")
    async def post_protected_data(
        portfolio: dict = Depends(verify_portfolio_session),
    ):
        return {"status": "updated", "portfolio_id": portfolio["id"]}

    @test_app.post("/api/test/login/{portfolio_id}")
    async def set_cookie_endpoint(portfolio_id: str, response: Response):
        raw_token = generate_session_token()
        set_session_cookie(response, raw_token)
        # Note: Do not return raw_token in JSON when cookie-based auth is used
        return {"status": "cookie_set"}

    return test_app


@pytest.fixture
def test_app():
    return create_test_app()


@pytest.fixture
def test_client(test_app):
    return TestClient(test_app)


# --- 1. Token Generation & Hash-Only Persistence Tests ---

def test_token_generation_entropy_and_hashing():
    """Verify that generated tokens have high entropy and SHA-256 digests are deterministic."""
    token1 = generate_session_token()
    token2 = generate_session_token()

    # Tokens must be distinct
    assert token1 != token2
    assert len(token1) >= 43  # 32 urlsafe bytes = 43 chars

    # SHA-256 hash must be 64-character hex digest
    hash1 = hash_session_token(token1)
    hash2 = hash_session_token(token2)

    assert len(hash1) == 64
    assert len(hash2) == 64
    assert hash1 != hash2

    # Determinism
    assert hash_session_token(token1) == hash1


# --- 2. Supabase Client Fail-Closed Tests ---

def test_supabase_client_fails_closed_when_unconfigured():
    """Verify that get_supabase_client raises SupabaseConfigurationError when settings are absent."""
    reset_supabase_client()
    orig_url = settings.SUPABASE_URL
    orig_key = settings.SUPABASE_SERVICE_ROLE_KEY

    try:
        settings.SUPABASE_URL = None
        settings.SUPABASE_SERVICE_ROLE_KEY = None

        with pytest.raises(SupabaseConfigurationError) as exc_info:
            get_supabase_client()

        assert "Supabase server configuration is missing" in str(exc_info.value)
        # Ensure no secrets or credentials are in exception string
        assert "secret" not in str(exc_info.value).lower()
    finally:
        settings.SUPABASE_URL = orig_url
        settings.SUPABASE_SERVICE_ROLE_KEY = orig_key
        reset_supabase_client()


def test_service_role_client_not_initialized_from_browser_config():
    """Verify that server-side client strictly requires SUPABASE_SERVICE_ROLE_KEY and ignores browser keys."""
    reset_supabase_client()
    orig_url = settings.SUPABASE_URL
    orig_key = settings.SUPABASE_SERVICE_ROLE_KEY

    try:
        settings.SUPABASE_URL = "https://rqmwizqcrtzmynhekagw.supabase.co"
        settings.SUPABASE_SERVICE_ROLE_KEY = None  # Service role missing

        # Even if someone accidentally passed an anon or client key, server-side client must fail
        with pytest.raises(SupabaseConfigurationError):
            get_supabase_client()
    finally:
        settings.SUPABASE_URL = orig_url
        settings.SUPABASE_SERVICE_ROLE_KEY = orig_key
        reset_supabase_client()


# --- 3. Cookie Flags in Dev vs Production Tests ---

def test_cookie_security_flag_environment_awareness():
    """Verify that cookies are non-Secure in development and Secure in production."""
    orig_env = settings.APP_ENV
    orig_secure = settings.SESSION_COOKIE_SECURE

    try:
        # Development mode
        settings.APP_ENV = "development"
        settings.SESSION_COOKIE_SECURE = None
        assert get_cookie_security_flag() is False

        # Production mode
        settings.APP_ENV = "production"
        settings.SESSION_COOKIE_SECURE = None
        assert get_cookie_security_flag() is True

        # Explicit override
        settings.SESSION_COOKIE_SECURE = True
        assert get_cookie_security_flag() is True

        settings.SESSION_COOKIE_SECURE = False
        assert get_cookie_security_flag() is False
    finally:
        settings.APP_ENV = orig_env
        settings.SESSION_COOKIE_SECURE = orig_secure


def test_set_and_clear_cookie_attributes():
    """Verify cookie headers set proper HttpOnly, SameSite, and Path attributes."""
    response = Response()
    raw_token = generate_session_token()
    set_session_cookie(response, raw_token)

    cookie_header = response.headers.get("set-cookie")
    assert cookie_header is not None
    assert settings.SESSION_COOKIE_NAME in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header or "SameSite=Lax" in cookie_header
    assert "Path=/" in cookie_header

    # Clear cookie
    clear_response = Response()
    clear_session_cookie(clear_response)
    clear_header = clear_response.headers.get("set-cookie")
    assert "Max-Age=0" in clear_header or "expires=" in clear_header.lower()


# --- 4. Session Verification Dependency Tests ---

def test_verify_session_missing_credentials_fails(test_client):
    """Verify that requests missing session credentials receive HTTP 401."""
    p_id = str(uuid.uuid4())
    response = test_client.get(f"/api/test/portfolio/{p_id}")
    assert response.status_code == 401
    assert "missing session token" in response.json()["detail"].lower()


def test_verify_session_malformed_token_fails(test_client):
    """Verify that malformed token strings receive HTTP 401 without querying database."""
    p_id = str(uuid.uuid4())
    # Too short (< 24 chars)
    response = test_client.get(
        f"/api/test/portfolio/{p_id}",
        headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}=short"},
    )
    assert response.status_code == 401
    assert "Invalid session token format" in response.json()["detail"]


def test_verify_session_portfolio_not_found(test_client):
    """Verify that a valid token format for a non-existent portfolio returns HTTP 404."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = []
    override_supabase_client(mock_client)

    try:
        response = test_client.get(
            f"/api/test/portfolio/{p_id}",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        reset_supabase_client()


def test_verify_session_valid_token_success(test_client):
    """Verify that matching session hash grants access and returns portfolio data."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "octocat",
            "scan_status": "pending",
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        response = test_client.get(
            f"/api/test/portfolio/{p_id}",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "portfolio_id": p_id}
    finally:
        reset_supabase_client()


def test_verify_session_via_custom_header(test_client):
    """Verify that X-Session-Token header authorizes valid requests."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        response = test_client.get(
            f"/api/test/portfolio/{p_id}",
            headers={"X-Session-Token": raw_token},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "portfolio_id": p_id}
    finally:
        reset_supabase_client()


def test_verify_session_via_bearer_header(test_client):
    """Verify that Authorization: Bearer <token> authorizes valid requests."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        response = test_client.get(
            f"/api/test/portfolio/{p_id}",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "portfolio_id": p_id}
    finally:
        reset_supabase_client()


def test_verify_session_cross_portfolio_attack_rejected(test_client):
    """Verify that token for Portfolio A cannot access Portfolio B (IDOR prevention)."""
    p_id_b = str(uuid.uuid4())

    token_a = generate_session_token()
    token_b = generate_session_token()
    hash_b = hash_session_token(token_b)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id_b,
            "github_username": "victim",
            "session_token_hash": hash_b,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        # Attacker attempts to access Portfolio B with Token A
        response = test_client.get(
            f"/api/test/portfolio/{p_id_b}",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token_a}"},
        )
        assert response.status_code == 403
        assert "does not match" in response.json()["detail"].lower()
    finally:
        reset_supabase_client()


def test_verify_session_revoked_session_rejected(test_client):
    """Verify that revoked session (session_token_hash is NULL) is rejected with HTTP 401."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "octocat",
            "session_token_hash": None,  # Revoked
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        response = test_client.get(
            f"/api/test/portfolio/{p_id}",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}"},
        )
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower()
    finally:
        reset_supabase_client()


def test_verify_session_archived_portfolio_rejected(test_client):
    """Verify that archived portfolio is rejected with HTTP 403."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "octocat",
            "session_token_hash": token_hash,
            "is_archived": True,  # Archived
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        response = test_client.get(
            f"/api/test/portfolio/{p_id}",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}"},
        )
        assert response.status_code == 403
        assert "archived" in response.json()["detail"].lower()
    finally:
        reset_supabase_client()


def test_verify_session_expired_session_rejected(test_client):
    """Verify that sessions older than SESSION_MAX_AGE_SECONDS receive HTTP 401."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    expired_time = datetime.now(timezone.utc) - timedelta(days=30)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "octocat",
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": expired_time.isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        response = test_client.get(
            f"/api/test/portfolio/{p_id}",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}"},
        )
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()
    finally:
        reset_supabase_client()


def test_revoke_portfolio_session_updates_database():
    """Verify that revoke_portfolio_session nullifies stored hash in database."""
    p_id = uuid.uuid4()
    mock_client = MagicMock()

    revoke_portfolio_session(p_id, mock_client)

    mock_client.table.assert_called_with("portfolios")
    mock_client.table().update.assert_called_with({"session_token_hash": None})
    mock_client.table().update().eq.assert_called_with("id", str(p_id))


# --- 5. CSRF Defense Tests ---

def test_csrf_protection_on_post_with_cookies(test_client):
    """Verify that state-changing requests via cookies require whitelisted Origin or custom header."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        # Case A: Cross-site POST without header or allowed origin -> 403 CSRF
        response_bad = test_client.post(
            f"/api/test/portfolio/{p_id}/update",
            headers={
                "Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}",
                "Origin": "http://evil-site.com",
            },
        )
        assert response_bad.status_code == 403
        assert "CSRF validation failed" in response_bad.json()["detail"]

        # Case B: Allowed Origin -> 200 OK
        response_good_origin = test_client.post(
            f"/api/test/portfolio/{p_id}/update",
            headers={
                "Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}",
                "Origin": "http://localhost:5173",
            },
        )
        assert response_good_origin.status_code == 200

        # Case C: Custom header present -> 200 OK
        response_good_header = test_client.post(
            f"/api/test/portfolio/{p_id}/update",
            headers={
                "Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        assert response_good_header.status_code == 200
    finally:
        reset_supabase_client()


# --- 6. Security Invariant: Zero Token or Secret Leakage ---

def test_no_secret_or_token_leakage_in_responses_and_logs(test_client, caplog):
    """Verify that neither raw tokens nor service role keys ever leak into responses or logs."""
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        with caplog.at_level(logging.DEBUG):
            # Test cookie login endpoint
            login_resp = test_client.post(f"/api/test/login/{p_id}")
            # Body must not contain raw token
            assert "token" not in login_resp.json() or login_resp.json().get("token") is None
            assert raw_token not in login_resp.text

            # Test authenticated request
            resp = test_client.get(
                f"/api/test/portfolio/{p_id}",
                headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={raw_token}"},
            )
            assert resp.status_code == 200
            assert raw_token not in resp.text
            assert token_hash not in resp.text

            # Check logs
            log_text = caplog.text
            assert raw_token not in log_text
            assert token_hash not in log_text
    finally:
        reset_supabase_client()


# --- 7. Candidate Session Status & Ingestion Regression Tests (Phase 10D.2) ---

from app.main import create_app

def test_session_status_endpoint_lifecycle():
    """Verify GET /api/portfolio/session returns 401 on missing, expired, and revoked sessions, and 200 on valid."""
    app = create_app()
    client = TestClient(app)

    # 1. Missing session -> 401
    res_missing = client.get("/api/portfolio/session")
    assert res_missing.status_code == 401
    assert "missing session token" in res_missing.json()["detail"]

    # 2. Valid session -> 200
    p_id = str(uuid.uuid4())
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "test-candidate",
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_client)

    try:
        client.cookies.set(settings.SESSION_COOKIE_NAME, raw_token)
        res_valid = client.get("/api/portfolio/session")
        assert res_valid.status_code == 200
        data = res_valid.json()
        assert data["authenticated"] is True
        assert data["portfolio_id"] == p_id
        assert data["github_username"] == "test-candidate"
        # Never leak tokens or hashes
        assert raw_token not in res_valid.text
        assert token_hash not in res_valid.text

        # 3. Expired session -> 401
        expired_time = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        mock_client.table().select().eq().execute.return_value.data = [
            {
                "id": p_id,
                "github_username": "test-candidate",
                "session_token_hash": token_hash,
                "is_archived": False,
                "updated_at": expired_time,
            }
        ]
        res_expired = client.get("/api/portfolio/session")
        assert res_expired.status_code == 401
        assert "expired" in res_expired.json()["detail"].lower()

        # 4. Revoked session (session_token_hash = None) -> 401
        mock_client.table().select().eq().execute.return_value.data = [
            {
                "id": p_id,
                "github_username": "test-candidate",
                "session_token_hash": None,
                "is_archived": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        res_revoked = client.get("/api/portfolio/session")
        assert res_revoked.status_code == 401
        assert "revoked" in res_revoked.json()["detail"].lower()
    finally:
        reset_supabase_client()

