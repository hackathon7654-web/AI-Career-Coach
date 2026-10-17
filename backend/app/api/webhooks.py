"""
ProofPath AI — GitHub Webhook & Candidate Activity API Router
Endpoints:
- POST /api/webhooks/github : Public GitHub webhook endpoint with HMAC-SHA256 verification
- GET /api/portfolio/{portfolio_id}/activity : Retrieve persisted webhook deliveries for candidate repositories
- POST /api/portfolio/{portfolio_id}/simulate-push : Local test simulation for push events
"""
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.session import verify_portfolio_session
from app.core.supabase import get_supabase_client
from app.schemas.webhook import (
    ActivityResponse,
    WebhookDeliveryItem,
    WebhookResponse,
)
from app.services.webhook_service import (
    WebhookVerificationError,
    get_webhook_service,
    verify_github_signature,
)

logger = logging.getLogger("proofpath_ai.api.webhooks")

router = APIRouter(tags=["GitHub Webhooks & Activity"])


class SimulatePushRequest(BaseModel):
    """Payload to trigger a local simulated push event for candidate testing."""
    repository_name: str = Field(..., description="Repository full_name (e.g. octocat/hello-world).")
    commit_sha: Optional[str] = Field(None, description="Optional target commit SHA (default generated).")
    commit_message: str = Field("Update implementation for candidate evaluation", description="Commit message.")
    changed_paths: List[str] = Field(
        default_factory=lambda: ["src/index.ts"],
        description="List of modified or added file paths.",
    )


@router.post(
    "/api/webhooks/github",
    response_model=WebhookResponse,
    summary="GitHub push webhook receiver with HMAC-SHA256 verification",
)
async def github_webhook(
    request: Request,
) -> WebhookResponse:
    """
    Receives inbound GitHub push events.
    Verifies HMAC-SHA256 signature against GITHUB_WEBHOOK_SECRET.
    Enforces delivery idempotency, matches verified repository identity,
    and initiates bounded scanning and evidence-based reassessment.
    """
    x_github_event = request.headers.get("x-github-event")
    x_github_delivery = request.headers.get("x-github-delivery")
    x_hub_signature_256 = request.headers.get("x-hub-signature-256")

    # Ping handshake handling
    if x_github_event == "ping":
        return WebhookResponse(
            delivery_id=x_github_delivery or "ping",
            status="completed",
            message="GitHub webhook ping received successfully.",
        )

    # Process push events only
    if x_github_event != "push":
        return WebhookResponse(
            delivery_id=x_github_delivery or "unknown",
            status="ignored",
            message=f"Event '{x_github_event}' is not handled. ProofPath AI monitors push events.",
        )

    if not x_github_delivery:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required X-GitHub-Delivery header.",
        )

    # Read raw body for HMAC verification
    raw_body = await request.body()

    try:
        verify_github_signature(raw_body, x_hub_signature_256)
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    service = get_webhook_service()
    try:
        response = await service.handle_push_event(
            delivery_id=x_github_delivery,
            raw_body=raw_body,
            hmac_verified=True,
        )
        return response
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except Exception as exc:
        logger.error(f"Unexpected error processing webhook delivery {x_github_delivery}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook event.",
        )


@router.get(
    "/api/portfolio/{portfolio_id}/activity",
    response_model=ActivityResponse,
    summary="List persisted webhook deliveries and automatic reassessments",
)
async def get_portfolio_activity(
    portfolio_id: UUID,
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> ActivityResponse:
    """
    Retrieves the ledger of real GitHub webhook deliveries for candidate repositories.
    Includes delivery IDs, commit SHAs, changed paths, HMAC verification status, and reassessment states.
    """
    client = get_supabase_client()
    p_id_str = str(portfolio_id)

    # 1. Fetch candidate's tracked repositories
    try:
        repos_res = (
            client.table("repositories")
            .select("full_name")
            .eq("portfolio_id", p_id_str)
            .execute()
        )
        repo_names = [r["full_name"] for r in (repos_res.data or [])]
    except Exception as exc:
        logger.error(f"Error fetching candidate repositories for activity: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving activity.")

    if not repo_names:
        return ActivityResponse(portfolio_id=p_id_str, deliveries=[])

    # 2. Query repository_events for candidate's repositories
    try:
        events_res = (
            client.table("repository_events")
            .select("id, delivery_id, repository_name, event_type, commit_sha, changed_paths, received_at, hmac_verified, status, reassessment_run_id, retry_count, error_details, created_at")
            .in_("repository_name", repo_names)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        rows = events_res.data or []
    except Exception as exc:
        logger.error(f"Error querying repository_events for activity: {exc}")
        raise HTTPException(status_code=500, detail="Database error retrieving activity events.")

    items = [
        WebhookDeliveryItem(
            id=str(r.get("id")),
            delivery_id=r["delivery_id"],
            repository_name=r["repository_name"],
            event_type=r.get("event_type", "push"),
            commit_sha=r["commit_sha"],
            changed_paths=r.get("changed_paths") or [],
            received_at=r.get("received_at", ""),
            hmac_verified=r.get("hmac_verified", False),
            status=r.get("status", "completed"),
            reassessment_run_id=str(r["reassessment_run_id"]) if r.get("reassessment_run_id") else None,
            retry_count=r.get("retry_count", 0),
            error_details=r.get("error_details"),
            created_at=r.get("created_at"),
        )
        for r in rows
    ]

    return ActivityResponse(portfolio_id=p_id_str, deliveries=items)


@router.post(
    "/api/portfolio/{portfolio_id}/simulate-push",
    response_model=WebhookResponse,
    summary="Simulate a push event for candidate testing",
)
async def simulate_push_event(
    portfolio_id: UUID,
    payload: SimulatePushRequest,
    portfolio: Dict[str, Any] = Depends(verify_portfolio_session),
) -> WebhookResponse:
    """
    Executes a controlled push simulation for testing.
    Clearly marks delivery as simulated (hmac_verified=False, delivery_id starting with 'sim_').
    Updates evidence and executes real automatic reassessment.
    """
    delivery_id = f"sim_{uuid4().hex[:12]}"
    commit_sha = payload.commit_sha or hashlib.sha1(f"sim_commit_{uuid4().hex}".encode()).hexdigest()

    simulated_payload = {
        "ref": "refs/heads/main",
        "before": "0000000000000000000000000000000000000000",
        "after": commit_sha,
        "repository": {
            "name": payload.repository_name.split("/")[-1],
            "full_name": payload.repository_name,
            "default_branch": "main",
        },
        "commits": [
            {
                "id": commit_sha,
                "message": payload.commit_message,
                "added": [],
                "modified": payload.changed_paths,
                "removed": [],
            }
        ],
        "head_commit": {
            "id": commit_sha,
            "message": payload.commit_message,
            "added": [],
            "modified": payload.changed_paths,
            "removed": [],
        },
        "deleted": False,
    }

    raw_body = json.dumps(simulated_payload).encode("utf-8")
    service = get_webhook_service()

    try:
        response = await service.handle_push_event(
            delivery_id=delivery_id,
            raw_body=raw_body,
            hmac_verified=False,  # Clearly identifies simulated delivery
        )
        return response
    except Exception as exc:
        logger.error(f"Error in simulated push for {delivery_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(exc)[:200]}")
