"""
ProofPath AI — Portfolio & Repository API Router
Endpoints:
- POST /api/portfolio/intake : Candidate intake session creation
- GET /api/portfolio/{portfolio_id}/repositories/discover : Discover public candidate repositories
- PATCH /api/portfolio/{portfolio_id}/repositories/select : Select repositories for evidence scanning
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.config import settings
from app.core.supabase import get_supabase_client
from app.core.session import (
    generate_session_token,
    get_authenticated_portfolio,
    hash_session_token,
    set_session_cookie,
    verify_portfolio_session,
)
from app.schemas.repository import (
    CandidateIntakeRequest,
    CandidateIntakeResponse,
    RepositoryDiscoveryResponse,
    RepositoryItem,
    RepositorySelectionRequest,
    RepositorySelectionResponse,
)
from app.services.github_client import (
    get_github_client,
    GitHubClientError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubSSRFError,
)

logger = logging.getLogger("proofpath_ai.api.portfolio")

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio & Repositories"])


@router.get(
    "/session",
    summary="Get current candidate session status",
)
async def get_current_session(
    caller_portfolio: Dict[str, Any] = Depends(get_authenticated_portfolio),
) -> Dict[str, Any]:
    """
    Returns verified candidate portfolio metadata from the active session.
    Fails closed with 401 if the caller has no valid session.
    Never exposes raw tokens or secrets.
    """
    return {
        "authenticated": True,
        "portfolio_id": str(caller_portfolio["id"]),
        "github_username": caller_portfolio.get("github_username", ""),
    }


@router.post(
    "/intake",
    response_model=CandidateIntakeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize candidate intake session",
)
async def candidate_intake(
    payload: CandidateIntakeRequest,
    response: Response,
) -> CandidateIntakeResponse:
    """
    Creates a new portfolio record and sets the candidate's HttpOnly session cookie.
    Validates GitHub username and initializes portfolio state to 'pending'.
    """
    client = get_supabase_client()
    username = payload.github_username
    profile_url = f"https://github.com/{username}"

    # Generate cryptographically secure session token and hash
    raw_token = generate_session_token()
    token_hash = hash_session_token(raw_token)

    # Persist portfolio record in Supabase
    try:
        insert_res = (
            client.table("portfolios")
            .insert({
                "github_username": username,
                "profile_url": profile_url,
                "scan_status": "pending",
                "session_token_hash": token_hash,
                "is_archived": False,
            })
            .execute()
        )
    except Exception as exc:
        logger.error(f"Failed to create portfolio record for {username}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize candidate portfolio session.",
        )

    if not insert_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist portfolio record.",
        )

    portfolio = insert_res.data[0]
    p_id = portfolio["id"]

    # Set secure HttpOnly candidate session cookie
    set_session_cookie(response, raw_token)

    return CandidateIntakeResponse(
        portfolio_id=str(p_id),
        github_username=portfolio["github_username"],
        profile_url=portfolio["profile_url"],
        scan_status=portfolio["scan_status"],
        created_at=portfolio["created_at"],
    )


@router.get(
    "/{portfolio_id}/repositories/discover",
    response_model=RepositoryDiscoveryResponse,
    summary="Discover candidate GitHub repositories",
)
async def discover_repositories(
    portfolio_id: UUID,
    page: int = Query(1, ge=1, le=settings.GITHUB_MAX_PAGES, description="Page number (max 5)"),
    per_page: int = Query(30, ge=1, le=settings.GITHUB_PER_PAGE_MAX, description="Items per page (max 50)"),
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> RepositoryDiscoveryResponse:
    """
    Fetches candidate's public repositories from GitHub with pagination bounds.
    Requires verified session for the exact portfolio ID.
    Persists discovered repositories into the database under portfolio ownership.
    """
    username = portfolio.get("github_username")
    if not username:
        raise HTTPException(status_code=400, detail="Portfolio record lacks github_username.")

    github = get_github_client()
    try:
        discovered = await github.get_user_repositories(username, page=page, per_page=per_page)
    except GitHubRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
    except GitHubNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"GitHub user '{username}' not found.")
    except GitHubSSRFError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except GitHubClientError as exc:
        raise HTTPException(status_code=exc.status_code or 502, detail=f"GitHub API error: {exc.message}")

    # Persist or update discovered repositories in Supabase
    db_client = get_supabase_client()
    p_id_str = str(portfolio_id)

    persisted_items: List[RepositoryItem] = []
    for repo in discovered:
        full_name = repo["full_name"]
        try:
            # Upsert into repositories table
            upsert_res = (
                db_client.table("repositories")
                .upsert(
                    {
                        "portfolio_id": p_id_str,
                        "name": repo["name"],
                        "full_name": full_name,
                        "html_url": repo["html_url"],
                        "description": repo["description"],
                        "default_branch": repo["default_branch"],
                        "language": repo["language"],
                        "stars": repo["stars"],
                        "is_eligible": repo["is_eligible"],
                        "skip_reason": repo["skip_reason"],
                        "is_selected": repo["is_selected"],
                    },
                    on_conflict="portfolio_id,full_name",
                )
                .execute()
            )
            saved_row = upsert_res.data[0] if upsert_res.data else None
            repo_id = saved_row["id"] if saved_row else None
            is_selected = saved_row["is_selected"] if saved_row else repo["is_selected"]

            persisted_items.append(
                RepositoryItem(
                    id=repo_id,
                    name=repo["name"],
                    full_name=full_name,
                    html_url=repo["html_url"],
                    description=repo["description"],
                    default_branch=repo["default_branch"],
                    language=repo["language"],
                    stars=repo["stars"],
                    is_eligible=repo["is_eligible"],
                    skip_reason=repo["skip_reason"],
                    is_selected=is_selected,
                )
            )
        except Exception as exc:
            logger.warning(f"Error persisting repository {full_name}: {exc}")
            # If persistence fails for one repo, still return the discovered item
            persisted_items.append(
                RepositoryItem(
                    id=None,
                    name=repo["name"],
                    full_name=full_name,
                    html_url=repo["html_url"],
                    description=repo["description"],
                    default_branch=repo["default_branch"],
                    language=repo["language"],
                    stars=repo["stars"],
                    is_eligible=repo["is_eligible"],
                    skip_reason=repo["skip_reason"],
                    is_selected=repo["is_selected"],
                )
            )

    return RepositoryDiscoveryResponse(
        portfolio_id=p_id_str,
        github_username=username,
        page=page,
        per_page=per_page,
        total_discovered=len(persisted_items),
        repositories=persisted_items,
    )


@router.patch(
    "/{portfolio_id}/repositories/select",
    response_model=RepositorySelectionResponse,
    summary="Update selected repositories for assessment",
)
async def select_repositories(
    portfolio_id: UUID,
    payload: RepositorySelectionRequest,
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> RepositorySelectionResponse:
    """
    Updates the candidate's repository scope selection.
    Enforces that all selected repository UUIDs belong strictly to this portfolio.
    Rejects any unverified or cross-portfolio repository IDs (IDOR protection).
    """
    p_id_str = str(portfolio_id)
    target_ids = [str(r_id) for r_id in payload.repository_ids]

    if len(target_ids) > settings.MAX_SELECTED_REPOSITORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot select more than {settings.MAX_SELECTED_REPOSITORIES} repositories simultaneously.",
        )

    db_client = get_supabase_client()

    # Verify that all target_ids actually belong to THIS portfolio
    check_res = (
        db_client.table("repositories")
        .select("id, is_eligible")
        .eq("portfolio_id", p_id_str)
        .in_("id", target_ids)
        .execute()
    )
    found_rows = check_res.data or []
    found_ids = {r["id"] for r in found_rows}

    # If any requested ID does not belong to this portfolio, reject immediately
    missing_or_forbidden = [t_id for t_id in target_ids if t_id not in found_ids]
    if missing_or_forbidden:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="One or more specified repositories do not belong to this candidate portfolio.",
        )

    # Fetch current selection state to compute atomic delta and prevent partial wipe
    current_res = (
        db_client.table("repositories")
        .select("id, is_selected")
        .eq("portfolio_id", p_id_str)
        .execute()
    )
    current_rows = current_res.data or []
    current_selected = {r["id"] for r in current_rows if r.get("is_selected")}
    target_set = set(target_ids)

    to_select = list(target_set - current_selected)
    to_unselect = list(current_selected - target_set)

    # Apply delta updates with rollback protection
    if to_select:
        try:
            db_client.table("repositories").update({"is_selected": True}).eq("portfolio_id", p_id_str).in_("id", to_select).execute()
        except Exception as exc:
            logger.error(f"Error selecting repositories for portfolio {p_id_str}: {exc}")
            raise HTTPException(status_code=500, detail="Failed to update repository selection.")

    if to_unselect:
        try:
            db_client.table("repositories").update({"is_selected": False}).eq("portfolio_id", p_id_str).in_("id", to_unselect).execute()
        except Exception as exc:
            logger.error(f"Error unselecting repositories for portfolio {p_id_str}: {exc}")
            # Rollback newly selected repos if unselecting fails
            if to_select:
                try:
                    db_client.table("repositories").update({"is_selected": False}).eq("portfolio_id", p_id_str).in_("id", to_select).execute()
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail="Failed to update repository selection.")

    # 3. Fetch all repositories to return updated state
    all_res = (
        db_client.table("repositories")
        .select("id, name, full_name, html_url, description, default_branch, language, stars, is_eligible, skip_reason, is_selected")
        .eq("portfolio_id", p_id_str)
        .order("is_selected", desc=True)
        .execute()
    )
    all_rows = all_res.data or []

    result_items = [
        RepositoryItem(
            id=r["id"],
            name=r["name"],
            full_name=r["full_name"],
            html_url=r["html_url"],
            description=r.get("description"),
            default_branch=r.get("default_branch", "main"),
            language=r.get("language"),
            stars=r.get("stars", 0),
            is_eligible=r.get("is_eligible", True),
            skip_reason=r.get("skip_reason"),
            is_selected=r.get("is_selected", False),
        )
        for r in all_rows
    ]

    selected_count = sum(1 for item in result_items if item.is_selected)

    return RepositorySelectionResponse(
        portfolio_id=p_id_str,
        selected_count=selected_count,
        repositories=result_items,
    )
