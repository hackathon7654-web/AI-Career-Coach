"""
ProofPath AI — GitHub REST API Client
Provides secure, bounded, authenticated/unauthenticated access to the GitHub REST API.
Enforces:
- Strict HTTPS and fixed GitHub API host (api.github.com)
- SSRF prevention (no arbitrary URLs, no redirects to untrusted hosts)
- Connection and read timeouts
- Bounded retries with backoff for transient 5xx / connection errors
- Rate-limit header parsing and fail-fast rate-limit exceptions
- Pagination bounds (max pages, max per_page)
- Zero secret logging
- Commit SHA resolution and git blob fetching
"""
import asyncio
import base64
import logging
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import httpx
from app.core.config import settings

logger = logging.getLogger("proofpath_ai.github")

ALLOWED_API_HOST = "api.github.com"


class GitHubClientError(Exception):
    """Base exception for GitHub API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GitHubRateLimitError(GitHubClientError):
    """Raised when GitHub rate limit is exceeded."""
    def __init__(self, reset_timestamp: Optional[int] = None, retry_after: Optional[int] = None):
        msg = "GitHub API rate limit exceeded. Please configure GITHUB_TOKEN or try again later."
        if retry_after:
            msg += f" (Retry after {retry_after}s)"
        elif reset_timestamp:
            msg += f" (Rate limit resets at epoch {reset_timestamp})"
        super().__init__(msg, status_code=429)
        self.reset_timestamp = reset_timestamp
        self.retry_after = retry_after


class GitHubNotFoundError(GitHubClientError):
    """Raised when the requested GitHub resource does not exist."""
    def __init__(self, resource: str):
        super().__init__(f"GitHub resource not found: {resource}", status_code=404)


class GitHubSSRFError(GitHubClientError):
    """Raised when a request violates SSRF or host allowlist restrictions."""
    def __init__(self, url: str):
        super().__init__(f"Request target rejected by SSRF security policy: {url}", status_code=400)


_TOKEN_DEFAULT = object()


class GitHubClient:
    """
    Asynchronous client for interacting with the GitHub REST API.
    """
    def __init__(
        self,
        token: Any = _TOKEN_DEFAULT,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.token = settings.GITHUB_TOKEN if token is _TOKEN_DEFAULT else token
        self.base_url = (base_url or settings.GITHUB_API_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.GITHUB_TIMEOUT_SECONDS
        self._custom_client = client

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ProofPath-AI/1.0",
        }
        if self.token:
            token_val = self.token.strip()
            if token_val.startswith("Bearer ") or token_val.startswith("token "):
                headers["Authorization"] = token_val
            else:
                # Modern GitHub REST API standard for OAuth & fine-grained PATs
                headers["Authorization"] = f"Bearer {token_val}"
        return headers

    def _validate_url(self, url: str) -> None:
        """
        SSRF check: Verifies that the URL strictly targets the approved GitHub API host.
        """
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            raise GitHubSSRFError(f"Insecure scheme: {parsed.scheme}. Only HTTPS is permitted.")
        if parsed.netloc.lower() != ALLOWED_API_HOST:
            raise GitHubSSRFError(f"Unauthorized target host: {parsed.netloc}. Only {ALLOWED_API_HOST} is permitted.")

    def _check_rate_limit(self, response: httpx.Response) -> None:
        """
        Inspects GitHub rate limit headers and raises GitHubRateLimitError if exhausted.
        """
        remaining = response.headers.get("x-ratelimit-remaining")
        reset_ts = response.headers.get("x-ratelimit-reset")
        retry_after = response.headers.get("retry-after")

        if response.status_code in (403, 429):
            if remaining == "0" or "rate limit" in response.text.lower() or retry_after:
                reset_val = int(reset_ts) if reset_ts and reset_ts.isdigit() else None
                retry_val = int(retry_after) if retry_after and retry_after.isdigit() else None
                logger.warning(f"GitHub rate limit reached: reset={reset_val}, retry_after={retry_val}")
                raise GitHubRateLimitError(reset_timestamp=reset_val, retry_after=retry_val)

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> httpx.Response:
        """
        Executes a bounded HTTP request with retry logic for transient failures.
        """
        if path.startswith("http://") or path.startswith("https://"):
            full_url = path
        else:
            full_url = f"{self.base_url}/{path.lstrip('/')}"

        self._validate_url(full_url)
        headers = self._get_headers()

        timeout_config = httpx.Timeout(self.timeout, connect=5.0)

        attempt = 0
        backoff = 0.5

        while attempt < max_retries:
            attempt += 1
            try:
                if self._custom_client:
                    response = await self._custom_client.request(
                        method,
                        full_url,
                        params=params,
                        headers=headers,
                        timeout=timeout_config,
                        follow_redirects=False,
                    )
                else:
                    async with httpx.AsyncClient(timeout=timeout_config, follow_redirects=False) as client:
                        response = await client.request(
                            method,
                            full_url,
                            params=params,
                            headers=headers,
                        )

                # Check for redirects to external hosts (SSRF defense)
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    self._validate_url(location)
                    # Redirect on api.github.com can be retried to new path if safe
                    return await self._request(method, location, params=None, max_retries=max_retries - 1)

                # Rate limit inspection
                self._check_rate_limit(response)

                # Handle 404 Not Found
                if response.status_code == 404:
                    raise GitHubNotFoundError(path)

                # Handle transient 5xx server errors with backoff
                if response.status_code in (500, 502, 503, 504) and attempt < max_retries:
                    logger.warning(
                        f"GitHub API {response.status_code} transient error on {path} (attempt {attempt}/{max_retries}). Retrying..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                if response.status_code >= 400:
                    # Sanitize message - never expose internal tokens or secret payloads
                    if response.status_code == 401:
                        err_msg = "GitHub API authentication failed (401 Bad credentials). The configured GITHUB_TOKEN is invalid, expired, or revoked."
                    elif response.status_code == 403:
                        err_msg = "GitHub API authorization failed (403 Forbidden). Token lacks necessary repository permissions."
                    else:
                        err_msg = f"GitHub API error {response.status_code}"
                        try:
                            err_json = response.json()
                            if "message" in err_json:
                                err_msg += f": {err_json['message']}"
                        except Exception:
                            pass
                    raise GitHubClientError(err_msg, status_code=response.status_code)

                return response

            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                if attempt < max_retries:
                    logger.warning(
                        f"GitHub network timeout on {path} (attempt {attempt}/{max_retries}): {exc}. Retrying..."
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    raise GitHubClientError(
                        f"GitHub API connection failed after {max_retries} attempts.",
                        status_code=504,
                    )
            except GitHubClientError:
                raise
            except Exception as exc:
                raise GitHubClientError(f"Unexpected error querying GitHub: {str(exc)}", status_code=500)

        raise GitHubClientError(f"GitHub request failed after {max_retries} attempts.", status_code=504)

    async def get_user_repositories(
        self,
        username: str,
        page: int = 1,
        per_page: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Discovers public repositories for a candidate's GitHub username with pagination bounds.
        """
        # Strict validation
        clean_user = username.strip()
        safe_page = max(1, min(page, settings.GITHUB_MAX_PAGES))
        safe_per_page = max(1, min(per_page, settings.GITHUB_PER_PAGE_MAX))

        path = f"users/{clean_user}/repos"
        params = {
            "type": "public",
            "sort": "pushed",
            "direction": "desc",
            "page": safe_page,
            "per_page": safe_per_page,
        }

        response = await self._request("GET", path, params=params)
        raw_repos = response.json()

        if not isinstance(raw_repos, list):
            return []

        normalized_repos = []
        for repo in raw_repos:
            is_fork = repo.get("fork", False)
            is_archived = repo.get("archived", False)
            size = repo.get("size", 0)

            # Determine qualification & eligibility
            is_eligible = True
            skip_reason = None

            if is_fork:
                is_eligible = False
                skip_reason = "Forked repository (original authorship required for evaluation)."
            elif is_archived:
                is_eligible = False
                skip_reason = "Archived repository (read-only project)."
            elif size == 0:
                is_eligible = False
                skip_reason = "Empty repository."

            normalized = {
                "name": repo.get("name", ""),
                "full_name": repo.get("full_name", ""),
                "html_url": repo.get("html_url", ""),
                "description": repo.get("description") or "",
                "default_branch": repo.get("default_branch") or "main",
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count", 0),
                "is_eligible": is_eligible,
                "skip_reason": skip_reason,
                "is_selected": is_eligible,  # Eligible repos pre-selected by default
            }
            normalized_repos.append(normalized)

        return normalized_repos

    async def get_latest_commit_sha(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
    ) -> str:
        """
        Resolves the exact 40-character commit SHA for the specified branch head.
        Ensures immutable snapshot scanning.
        """
        path = f"repos/{owner}/{repo}/commits/{branch}"
        response = await self._request("GET", path)
        data = response.json()
        sha = data.get("sha")
        if not sha or len(sha) < 40:
            raise GitHubClientError(f"Unable to resolve valid commit SHA for {owner}/{repo}@{branch}", status_code=502)
        return sha

    async def get_git_tree(
        self,
        owner: str,
        repo: str,
        commit_sha: str,
        recursive: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetches the complete Git file tree pinned to a specific commit SHA.
        """
        path = f"repos/{owner}/{repo}/git/trees/{commit_sha}"
        params = {"recursive": "1"} if recursive else {}
        response = await self._request("GET", path, params=params)
        data = response.json()
        tree = data.get("tree", [])
        return tree

    async def get_blob_content(
        self,
        owner: str,
        repo: str,
        blob_sha: str,
        max_bytes: int = 512000,
    ) -> Tuple[str, int]:
        """
        Fetches and decodes git blob content pinned to its blob SHA.
        Returns (decoded_text, raw_size_bytes).
        Enforces max_bytes limits to prevent buffer memory exhaustion.
        """
        path = f"repos/{owner}/{repo}/git/blobs/{blob_sha}"
        response = await self._request("GET", path)
        data = response.json()

        size = data.get("size", 0)
        if size > max_bytes:
            raise GitHubClientError(f"File size ({size} bytes) exceeds safety limit ({max_bytes} bytes).", status_code=413)

        encoding = data.get("encoding", "base64")
        raw_content = data.get("content", "")

        if encoding == "base64":
            try:
                decoded_bytes = base64.b64decode(raw_content)
                text = decoded_bytes.decode("utf-8", errors="replace")
                return text, len(decoded_bytes)
            except Exception as exc:
                raise GitHubClientError(f"Failed to decode base64 git blob: {exc}", status_code=500)
        else:
            return raw_content, len(raw_content.encode("utf-8"))


# Singleton client instance
_default_github_client: Optional[GitHubClient] = None


def get_github_client() -> GitHubClient:
    """Provides singleton GitHub client instance."""
    global _default_github_client
    if _default_github_client is None:
        _default_github_client = GitHubClient()
    return _default_github_client


def override_github_client(client: GitHubClient) -> None:
    """Allows test fixtures to inject a mocked GitHubClient."""
    global _default_github_client
    _default_github_client = client


def reset_github_client() -> None:
    """Resets the GitHub client singleton."""
    global _default_github_client
    _default_github_client = None
