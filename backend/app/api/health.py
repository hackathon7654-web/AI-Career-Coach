from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/api/health")
@router.get("/health")
async def get_health():
    """
    Deterministic health check endpoint.
    Reports operational status of the API server without leaking sensitive internals or credentials.
    """
    return {
        "status": "ok",
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "not_configured" if not settings.SUPABASE_URL else "configured",
        "llm": "not_configured" if not settings.LLM_API_KEY else "configured",
        "github": "configured" if settings.GITHUB_TOKEN else "unauthenticated",
    }
