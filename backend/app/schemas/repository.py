"""
ProofPath AI — Repository & Candidate Intake Schemas
Defines request and response schemas for candidate intake, repository discovery, and repository selection.
"""
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator
import re

from urllib.parse import urlparse

GITHUB_USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$")
RESERVED_GITHUB_PATHS = {
    "about", "collections", "contact", "customer-stories", "enterprise", "events",
    "explore", "features", "git-guides", "issues", "join", "login", "marketplace",
    "mobile", "nonprofit", "organizations", "orgs", "pricing", "pulls", "readme",
    "security", "settings", "site", "sponsors", "team", "topics", "trending",
}


def parse_github_profile_username(raw_input: str) -> str:
    """
    Parses and normalizes a candidate GitHub handle from either:
    - Raw username: 'octocat' or '@octocat'
    - Full GitHub profile URL: 'https://github.com/octocat', 'https://github.com/octocat/', 'github.com/octocat'
    
    Rejects:
    - Non-GitHub hosts (e.g. 'gitlab.com/octocat')
    - Repository or sub-paths (e.g. 'https://github.com/octocat/my-repo')
    - Reserved GitHub system paths (e.g. 'features', 'pricing', 'orgs')
    - URL schemes other than http/https
    - Embedded credentials
    - Malformed usernames
    """
    clean = raw_input.strip()
    if not clean:
        raise ValueError("GitHub username or profile URL cannot be empty.")

    if "://" in clean or clean.lower().startswith(("github.com/", "www.github.com/")):
        candidate_url = clean if "://" in clean else f"https://{clean}"
        try:
            parsed = urlparse(candidate_url)
        except Exception:
            raise ValueError("Malformed GitHub profile URL.")

        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(f"Unsupported scheme '{parsed.scheme}'. Only http and https URLs are accepted.")

        if parsed.username or parsed.password:
            raise ValueError("Credentials in GitHub URLs are not permitted.")

        host = (parsed.hostname or "").lower()
        if host not in ("github.com", "www.github.com"):
            raise ValueError(f"Invalid host '{host}'. Only github.com profile URLs are supported.")

        path_parts = [p for p in parsed.path.split("/") if p]
        if not path_parts:
            raise ValueError("GitHub profile URL must contain a username (e.g. https://github.com/octocat).")
        if len(path_parts) > 1:
            raise ValueError(
                f"URL points to a repository or sub-resource ('/{'/'.join(path_parts)}'). "
                "Please provide a candidate profile URL (e.g. https://github.com/octocat) or username."
            )

        username = path_parts[0]
    else:
        username = clean.lstrip("@")

    if username.lower() in RESERVED_GITHUB_PATHS:
        raise ValueError(f"'{username}' is a reserved GitHub system path and not a valid candidate profile.")

    if not GITHUB_USERNAME_REGEX.match(username):
        raise ValueError(
            f"Invalid GitHub username '{username}'. Must contain only alphanumeric characters or single hyphens, "
            "and cannot begin or end with a hyphen (1-39 chars)."
        )

    return username


class CandidateIntakeRequest(BaseModel):
    """Payload to initiate a candidate intake session."""
    github_username: str = Field(
        ...,
        min_length=1,
        max_length=250,
        description="Candidate GitHub username or profile URL.",
        examples=["octocat", "https://github.com/octocat"],
    )

    @field_validator("github_username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        return parse_github_profile_username(v)


class CandidateIntakeResponse(BaseModel):
    """Response returned upon creating a candidate intake session."""
    portfolio_id: str
    github_username: str
    profile_url: str
    scan_status: str
    created_at: str
    message: str = "Candidate session initialized. Cookie set."


class RepositoryItem(BaseModel):
    """Normalized repository item matching database and UI schema."""
    id: Optional[str] = Field(None, description="Internal database UUID if persisted.")
    name: str = Field(..., description="Repository name.")
    full_name: str = Field(..., description="Full repository name e.g. octocat/Hello-World.")
    html_url: str = Field(..., description="HTTPS URL to GitHub repository.")
    description: Optional[str] = Field(None, description="Repository description.")
    default_branch: str = Field("main", description="Default branch name.")
    language: Optional[str] = Field(None, description="Primary detected programming language.")
    stars: int = Field(0, description="Stargazer count.")
    is_eligible: bool = Field(True, description="True if repository meets qualification criteria.")
    skip_reason: Optional[str] = Field(None, description="Reason if repository is ineligible.")
    is_selected: bool = Field(False, description="Whether selected for assessment scanning.")
    last_commit_sha: Optional[str] = Field(None, description="Commit SHA of default branch.")


class RepositoryDiscoveryResponse(BaseModel):
    """Paginated repository discovery response."""
    portfolio_id: str
    github_username: str
    page: int
    per_page: int
    total_discovered: int
    repositories: List[RepositoryItem]


class RepositorySelectionRequest(BaseModel):
    """Payload to select repositories for evidence scanning."""
    repository_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of repository UUIDs to select for evaluation (max 10).",
    )


class RepositorySelectionResponse(BaseModel):
    """Response returned after updating repository selection."""
    portfolio_id: str
    selected_count: int
    repositories: List[RepositoryItem]
