import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.health import router as health_router
from app.api.portfolio import router as portfolio_router
from app.api.scans import router as scans_router
from app.api.jobs import router as jobs_router
from app.api.assessments import router as assessments_router
from app.api.webhooks import router as webhooks_router
from fastapi import HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException

# Configure basic structured logging (no secrets/tokens logged)
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("proofpath_ai")


def create_app() -> FastAPI:
    """
    Application factory for ProofPath AI FastAPI backend.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
        description="ProofPath AI Backend API — Evidence-grounded career validation engine.",
    )

    # CORS configuration
    # Explicit origins only; no wildcard allowed when credentials or headers are present
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.FRONTEND_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
    )

    # Include API Routers
    app.include_router(health_router)
    app.include_router(portfolio_router)
    app.include_router(scans_router)
    app.include_router(jobs_router)
    app.include_router(assessments_router)
    app.include_router(webhooks_router)

    # Global Exception Handler (prevents leaking stack traces or internal config in production)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # Preserve deliberate HTTP exceptions
        if isinstance(exc, (HTTPException, StarletteHTTPException)):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=getattr(exc, "headers", None),
            )

        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {str(exc)}",
            exc_info=settings.DEBUG,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."},
        )

    return app


app = create_app()
