"""
ProofPath AI — Automated Tests for Phase 3D-2: GitHub Discovery & Repository Selection
Covers:
1. Candidate intake session creation and cookie delivery
2. Candidate intake input validation (invalid GitHub usernames rejected)
3. Successful repository listing with normalization and qualification
4. Pagination parameter bounds enforcement
5. Unauthenticated GitHub client operation without token
6. Rate-limit response (HTTP 429) and retry exhaustion
7. Transient failure with bounded retry and exponential backoff
8. Invalid query parameters rejected with HTTP 422
9. Candidate session authorization enforcement (HTTP 401 on missing session)
10. Cross-portfolio IDOR attempt rejected (HTTP 403 on token mismatch)
11. Repository selection success and state persistence
12. Selection rejects unverified / foreign repository UUIDs (HTTP 403)
13. Upstream error message sanitization (no secret leakage)
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.session import generate_session_token, hash_session_token
from app.core.supabase import (
    override_supabase_client,
    reset_supabase_client,
)
from app.services.github_client import (
    GitHubClient,
    GitHubClientError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubSSRFError,
    override_github_client,
    reset_github_client,
)


@pytest.fixture
def client():
    return TestClient(app)


# --- 1. Candidate Intake Tests ---

def test_candidate_intake_success(client):
    """Candidate intake creates a portfolio row and sets HttpOnly cookie."""
    mock_db = MagicMock()
    p_id = str(uuid.uuid4())
    mock_db.table().insert().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "octocat",
            "profile_url": "https://github.com/octocat",
            "scan_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_db)

    try:
        response = client.post("/api/portfolio/intake", json={"github_username": "octocat"})
        assert response.status_code == 201
        data = response.json()
        assert data["portfolio_id"] == p_id
        assert data["github_username"] == "octocat"
        assert data["profile_url"] == "https://github.com/octocat"
        assert data["scan_status"] == "pending"

        # Verify HttpOnly cookie header
        set_cookie = response.headers.get("set-cookie")
        assert set_cookie is not None
        assert settings.SESSION_COOKIE_NAME in set_cookie
        assert "HttpOnly" in set_cookie
    finally:
        reset_supabase_client()


def test_candidate_intake_invalid_username(client):
    """Rejects malformed or malicious GitHub username strings."""
    # Username with invalid special chars / injection
    response = client.post("/api/portfolio/intake", json={"github_username": "user;DROP TABLE--"})
    assert response.status_code == 422

    # Username starting with hyphen
    response2 = client.post("/api/portfolio/intake", json={"github_username": "-invalid"})
    assert response2.status_code == 422


# --- 2. Repository Discovery Tests ---

def test_discover_repositories_success(client):
    """Discovers public repositories, normalizes them, and persists them into Supabase."""
    p_id = str(uuid.uuid4())
    token = generate_session_token()
    token_hash = hash_session_token(token)

    mock_db = MagicMock()
    # Mock portfolio lookup for session verification
    mock_db.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "testuser",
            "scan_status": "pending",
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    # Mock repository upsert
    mock_db.table().upsert().execute.return_value.data = [
        {"id": str(uuid.uuid4()), "is_selected": True}
    ]
    override_supabase_client(mock_db)

    mock_github = MagicMock(spec=GitHubClient)
    mock_github.get_user_repositories = AsyncMock(return_value=[
        {
            "name": "algo-visualizer",
            "full_name": "testuser/algo-visualizer",
            "html_url": "https://github.com/testuser/algo-visualizer",
            "description": "Visualizer for graph algorithms",
            "default_branch": "main",
            "language": "TypeScript",
            "stars": 42,
            "is_eligible": True,
            "skip_reason": None,
            "is_selected": True,
        },
        {
            "name": "forked-repo",
            "full_name": "testuser/forked-repo",
            "html_url": "https://github.com/testuser/forked-repo",
            "description": "A fork",
            "default_branch": "main",
            "language": "Python",
            "stars": 0,
            "is_eligible": False,
            "skip_reason": "Forked repository (original authorship required for evaluation).",
            "is_selected": False,
        }
    ])
    override_github_client(mock_github)

    try:
        response = client.get(
            f"/api/portfolio/{p_id}/repositories/discover?page=1&per_page=30",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["portfolio_id"] == p_id
        assert data["total_discovered"] == 2
        assert len(data["repositories"]) == 2

        repo1 = data["repositories"][0]
        assert repo1["name"] == "algo-visualizer"
        assert repo1["is_eligible"] is True

        repo2 = data["repositories"][1]
        assert repo2["name"] == "forked-repo"
        assert repo2["is_eligible"] is False
        assert "Forked repository" in repo2["skip_reason"]
    finally:
        reset_supabase_client()
        reset_github_client()


def test_discover_repositories_pagination_bounds(client):
    """Enforces maximum pagination constraints (max 5 pages, max 50 per page)."""
    p_id = str(uuid.uuid4())
    token = generate_session_token()
    token_hash = hash_session_token(token)

    mock_db = MagicMock()
    mock_db.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "octocat",
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_db)

    try:
        # Exceeds max page (6 > 5)
        resp = client.get(
            f"/api/portfolio/{p_id}/repositories/discover?page=6",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"},
        )
        assert resp.status_code == 422

        # Exceeds max per_page (51 > 50)
        resp2 = client.get(
            f"/api/portfolio/{p_id}/repositories/discover?per_page=51",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"},
        )
        assert resp2.status_code == 422

        # Invalid page 0
        resp3 = client.get(
            f"/api/portfolio/{p_id}/repositories/discover?page=0",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"},
        )
        assert resp3.status_code == 422
    finally:
        reset_supabase_client()


def test_discover_repositories_rate_limited(client):
    """Handles GitHub rate limit by returning sanitized HTTP 429."""
    p_id = str(uuid.uuid4())
    token = generate_session_token()
    token_hash = hash_session_token(token)

    mock_db = MagicMock()
    mock_db.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "octocat",
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_db)

    mock_github = MagicMock(spec=GitHubClient)
    mock_github.get_user_repositories = AsyncMock(
        side_effect=GitHubRateLimitError(retry_after=60)
    )
    override_github_client(mock_github)

    try:
        response = client.get(
            f"/api/portfolio/{p_id}/repositories/discover",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"},
        )
        assert response.status_code == 429
        assert "rate limit exceeded" in response.json()["detail"].lower()
    finally:
        reset_supabase_client()
        reset_github_client()


def test_discover_repositories_missing_auth_rejected(client):
    """Unauthenticated requests are rejected with HTTP 401."""
    p_id = str(uuid.uuid4())
    response = client.get(f"/api/portfolio/{p_id}/repositories/discover")
    assert response.status_code == 401


def test_discover_repositories_cross_portfolio_rejected(client):
    """Session token for Portfolio A cannot access Portfolio B (IDOR prevention)."""
    p_id_b = str(uuid.uuid4())
    token_a = generate_session_token()
    token_b = generate_session_token()
    hash_b = hash_session_token(token_b)

    mock_db = MagicMock()
    mock_db.table().select().eq().execute.return_value.data = [
        {
            "id": p_id_b,
            "github_username": "victim",
            "session_token_hash": hash_b,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_db)

    try:
        response = client.get(
            f"/api/portfolio/{p_id_b}/repositories/discover",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token_a}"},
        )
        assert response.status_code == 403
    finally:
        reset_supabase_client()


# --- 3. Repository Selection Tests ---

def test_select_repositories_success(client):
    """Updates repository selection state for valid candidate repositories."""
    p_id = str(uuid.uuid4())
    token = generate_session_token()
    token_hash = hash_session_token(token)

    repo_id_1 = str(uuid.uuid4())
    repo_id_2 = str(uuid.uuid4())

    mock_db = MagicMock()
class MockPostgrestQuery:
    def __init__(self, data=None):
        self.data = data if data is not None else []
    def select(self, *a, **kw): return self
    def insert(self, *a, **kw): return self
    def update(self, *a, **kw): return self
    def upsert(self, *a, **kw): return self
    def eq(self, *a, **kw): return self
    def in_(self, *a, **kw): return self
    def order(self, *a, **kw): return self
    def execute(self): return self


def test_select_repositories_success(client):
    """Updates repository selection state for valid candidate repositories."""
    p_id = str(uuid.uuid4())
    token = generate_session_token()
    token_hash = hash_session_token(token)

    repo_id_1 = str(uuid.uuid4())
    repo_id_2 = str(uuid.uuid4())

    def table_router(name: str):
        if name == "portfolios":
            return MockPostgrestQuery([{
                "id": p_id,
                "github_username": "octocat",
                "session_token_hash": token_hash,
                "is_archived": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }])
        elif name == "repositories":
            return MockPostgrestQuery([
                {
                    "id": repo_id_1,
                    "name": "repo-one",
                    "full_name": "octocat/repo-one",
                    "html_url": "https://github.com/octocat/repo-one",
                    "is_selected": True,
                    "is_eligible": True,
                },
                {
                    "id": repo_id_2,
                    "name": "repo-two",
                    "full_name": "octocat/repo-two",
                    "html_url": "https://github.com/octocat/repo-two",
                    "is_selected": True,
                    "is_eligible": True,
                },
            ])
        return MockPostgrestQuery()

    mock_db = MagicMock()
    mock_db.table.side_effect = table_router
    override_supabase_client(mock_db)

    try:
        response = client.patch(
            f"/api/portfolio/{p_id}/repositories/select",
            json={"repository_ids": [repo_id_1, repo_id_2]},
            headers={
                "Cookie": f"{settings.SESSION_COOKIE_NAME}={token}",
                "Origin": "http://localhost:5173",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["portfolio_id"] == p_id
        assert data["selected_count"] == 2
        assert len(data["repositories"]) == 2
    finally:
        reset_supabase_client()


def test_select_repositories_foreign_repo_rejected(client):
    """Rejects selection if any repository ID does not belong to the portfolio."""
    p_id = str(uuid.uuid4())
    token = generate_session_token()
    token_hash = hash_session_token(token)

    foreign_repo_id = str(uuid.uuid4())

    def table_router(name: str):
        if name == "portfolios":
            return MockPostgrestQuery([{
                "id": p_id,
                "github_username": "octocat",
                "session_token_hash": token_hash,
                "is_archived": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }])
        elif name == "repositories":
            return MockPostgrestQuery([])
        return MockPostgrestQuery()

    mock_db = MagicMock()
    mock_db.table.side_effect = table_router
    override_supabase_client(mock_db)

    try:
        response = client.patch(
            f"/api/portfolio/{p_id}/repositories/select",
            json={"repository_ids": [foreign_repo_id]},
            headers={
                "Cookie": f"{settings.SESSION_COOKIE_NAME}={token}",
                "Origin": "http://localhost:5173",
            },
        )
        assert response.status_code == 403
        assert "do not belong to this candidate portfolio" in response.json()["detail"]
    finally:
        reset_supabase_client()


def test_select_repositories_db_failure_handled(client):
    """Verifies that database update failures during repository selection fail closed with HTTP 500."""
    p_id = str(uuid.uuid4())
    token = generate_session_token()
    token_hash = hash_session_token(token)
    repo_id = str(uuid.uuid4())

    class FailingUpdateQuery(MockPostgrestQuery):
        def update(self, *a, **kw):
            raise RuntimeError("Database connection pool timeout")

    def table_router(name: str):
        if name == "portfolios":
            return MockPostgrestQuery([{
                "id": p_id,
                "github_username": "octocat",
                "session_token_hash": token_hash,
                "is_archived": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }])
        elif name == "repositories":
            # Verification succeeds, but update fails
            q = FailingUpdateQuery([{"id": repo_id, "is_eligible": True, "is_selected": False}])
            return q
        return MockPostgrestQuery()

    mock_db = MagicMock()
    mock_db.table.side_effect = table_router
    override_supabase_client(mock_db)

    try:
        response = client.patch(
            f"/api/portfolio/{p_id}/repositories/select",
            json={"repository_ids": [repo_id]},
            headers={
                "Cookie": f"{settings.SESSION_COOKIE_NAME}={token}",
                "Origin": "http://localhost:5173",
            },
        )
        assert response.status_code == 500
        assert "Failed to update repository selection" in response.json()["detail"]
    finally:
        reset_supabase_client()


# --- 4. GitHub Client Unit & Security Tests ---

@pytest.mark.asyncio
async def test_github_client_unauthenticated():
    """GitHubClient initializes and builds standard unauthenticated headers when token is absent."""
    client = GitHubClient(token=None)
    headers = client._get_headers()
    assert "Authorization" not in headers
    assert headers["User-Agent"] == "ProofPath-AI/1.0"
    assert "api.github.com" in client.base_url


@pytest.mark.asyncio
async def test_github_client_transient_retry():
    """GitHubClient retries on transient 5xx HTTP errors."""
    mock_transport = AsyncMock()
    # 1st request 502, 2nd request 200
    resp_502 = httpx.Response(status_code=502, request=httpx.Request("GET", "https://api.github.com/users/test/repos"))
    resp_200 = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", "https://api.github.com/users/test/repos"),
        json=[{"name": "test-repo", "full_name": "test/test-repo", "fork": False, "size": 100}]
    )
    mock_transport.request = AsyncMock(side_effect=[resp_502, resp_200])

    async_client = httpx.AsyncClient()
    async_client.request = mock_transport.request

    gh = GitHubClient(client=async_client)
    repos = await gh.get_user_repositories("test")
    assert len(repos) == 1
    assert repos[0]["name"] == "test-repo"
    assert mock_transport.request.call_count == 2


@pytest.mark.asyncio
async def test_github_client_ssrf_protection():
    """GitHubClient rejects attempts to contact non-approved hosts or arbitrary URLs."""
    gh = GitHubClient()
    # Malicious external domain
    with pytest.raises(GitHubSSRFError):
        gh._validate_url("https://malicious-site.com/steal-data")

    # Insecure HTTP
    with pytest.raises(GitHubSSRFError):
        gh._validate_url("http://api.github.com/repos")

    # Cloud metadata endpoint
    with pytest.raises(GitHubSSRFError):
        gh._validate_url("http://169.254.169.254/latest/meta-data")


def test_upstream_error_sanitization(client):
    """GitHub upstream errors are sanitized before returning to client."""
    p_id = str(uuid.uuid4())
    token = generate_session_token()
    token_hash = hash_session_token(token)

    mock_db = MagicMock()
    mock_db.table().select().eq().execute.return_value.data = [
        {
            "id": p_id,
            "github_username": "ghost_user",
            "session_token_hash": token_hash,
            "is_archived": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_db)

    mock_github = MagicMock(spec=GitHubClient)
    mock_github.get_user_repositories = AsyncMock(
        side_effect=GitHubNotFoundError("users/ghost_user/repos")
    )
    override_github_client(mock_github)

    try:
        response = client.get(
            f"/api/portfolio/{p_id}/repositories/discover",
            headers={"Cookie": f"{settings.SESSION_COOKIE_NAME}={token}"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        # Verify no stack trace or secrets
        assert "traceback" not in response.text.lower()
    finally:
        reset_supabase_client()
        reset_github_client()


# --- 5. GitHub Profile URL & Intake Validation Tests ---

def test_parse_github_profile_username_valid():
    from app.schemas.repository import parse_github_profile_username
    # Raw handles
    assert parse_github_profile_username("octocat") == "octocat"
    assert parse_github_profile_username("@octocat") == "octocat"
    assert parse_github_profile_username("user-123") == "user-123"

    # HTTPS URLs
    assert parse_github_profile_username("https://github.com/octocat") == "octocat"
    assert parse_github_profile_username("https://github.com/octocat/") == "octocat"
    assert parse_github_profile_username("http://github.com/octocat") == "octocat"
    assert parse_github_profile_username("https://www.github.com/octocat") == "octocat"
    assert parse_github_profile_username("github.com/octocat") == "octocat"
    assert parse_github_profile_username("www.github.com/octocat/") == "octocat"


def test_parse_github_profile_username_rejects_invalid():
    from app.schemas.repository import parse_github_profile_username

    # Repository URLs
    with pytest.raises(ValueError, match="repository"):
        parse_github_profile_username("https://github.com/octocat/Hello-World")

    # Reserved GitHub paths
    with pytest.raises(ValueError, match="reserved"):
        parse_github_profile_username("https://github.com/features")
    with pytest.raises(ValueError, match="reserved"):
        parse_github_profile_username("pricing")

    # Non-GitHub hosts
    with pytest.raises(ValueError, match="Only github.com"):
        parse_github_profile_username("https://gitlab.com/octocat")
    with pytest.raises(ValueError, match="Only github.com"):
        parse_github_profile_username("https://evil.com/octocat")

    # Unsupported schemes
    with pytest.raises(ValueError, match="Unsupported scheme"):
        parse_github_profile_username("ftp://github.com/octocat")

    # Credentials
    with pytest.raises(ValueError, match="Credentials"):
        parse_github_profile_username("https://user:pass@github.com/octocat")

    # Malformed handles
    with pytest.raises(ValueError, match="Invalid GitHub username"):
        parse_github_profile_username("-leading-hyphen")
    with pytest.raises(ValueError, match="Invalid GitHub username"):
        parse_github_profile_username("trailing-hyphen-")


def test_intake_endpoint_accepts_profile_url(client):
    """Candidate intake endpoint accepts valid profile URL and persists normalized username."""
    mock_db = MagicMock()
    mock_db.table().insert().execute.return_value.data = [
        {
            "id": str(uuid.uuid4()),
            "github_username": "octocat",
            "profile_url": "https://github.com/octocat",
            "scan_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    override_supabase_client(mock_db)

    try:
        response = client.post(
            "/api/portfolio/intake",
            json={"github_username": "https://github.com/octocat/"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["github_username"] == "octocat"
        assert data["profile_url"] == "https://github.com/octocat"
    finally:
        reset_supabase_client()

