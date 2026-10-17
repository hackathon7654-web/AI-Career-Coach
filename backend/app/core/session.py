"""
ProofPath AI — Candidate Session Authorization Service
Implements cryptographically secure intake session lifecycle:
- High-entropy random tokens (secrets.token_urlsafe)
- SHA-256 hash persistence only
- Constant-time hash verification (hmac.compare_digest)
- Portfolio-scoped resource authorization
- HttpOnly, SameSite, Secure cookie handling
- CSRF defense-in-depth on state-changing cookie requests
- Zero leakage in logs, responses, and exceptions
"""
import hashlib
import hmac
import logging
import re
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import Request, Response, HTTPException, Depends
from supabase import Client
from app.core.config import settings
from app.core.supabase import get_supabase_client

logger = logging.getLogger("proofpath_ai.session")

# Regex pattern for validating token format (alphanumeric, dashes, underscores)
TOKEN_FORMAT_REGEX = re.compile(r"^[A-Za-z0-9_-]{24,128}$")


def generate_session_token() -> str:
    """
    Generates a cryptographically secure, high-entropy URL-safe session token.
    32 bytes of randomness produces 43 characters with 256 bits of entropy.
    """
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """
    Computes the SHA-256 hex digest of a raw session token.
    Only this digest is stored in the database.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_cookie_security_flag() -> bool:
    """
    Determines the Secure attribute for cookies.
    Defaults to False in local development, and True in staging/production.
    """
    if settings.SESSION_COOKIE_SECURE is not None:
        return settings.SESSION_COOKIE_SECURE
    return settings.APP_ENV != "development"


def set_session_cookie(response: Response, raw_token: str) -> None:
    """
    Sets the candidate intake session cookie on the outgoing response.
    Enforces HttpOnly, SameSite, and environment-aware Secure attributes.
    """
    is_secure = get_cookie_security_flag()
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        expires=settings.SESSION_MAX_AGE_SECONDS,
        path=settings.SESSION_COOKIE_PATH,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE.lower(),
        secure=is_secure,
    )


def clear_session_cookie(response: Response) -> None:
    """
    Clears the candidate intake session cookie upon logout or revocation.
    """
    is_secure = get_cookie_security_flag()
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path=settings.SESSION_COOKIE_PATH,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE.lower(),
        secure=is_secure,
    )


def extract_session_token(request: Request) -> tuple[Optional[str], str]:
    """
    Extracts the session token from incoming request.
    Returns (token, source) where source is 'cookie', 'header', or 'none'.
    """
    # Priority 1: Secure HttpOnly Cookie
    cookie_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token, "cookie"

    # Priority 2: Custom Header (for non-browser clients or API integrations)
    header_token = request.headers.get("X-Session-Token")
    if header_token:
        return header_token, "header"

    # Priority 3: Bearer Authorization Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip(), "header"

    return None, "none"


async def verify_portfolio_session(
    portfolio_id: UUID,
    request: Request,
) -> Dict[str, Any]:
    """
    FastAPI dependency enforcing candidate session authorization.
    Verifies that the caller possesses the session token matching THIS specific portfolio.
    Rejects missing, malformed, expired, revoked, or cross-portfolio requests.
    """
    token, source = extract_session_token(request)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: missing session token.",
            headers={"WWW-Authenticate": "Cookie"},
        )

    # Validate token format before database lookup
    if not TOKEN_FORMAT_REGEX.match(token):
        logger.warning(f"Rejected malformed session token for portfolio_id={portfolio_id}")
        raise HTTPException(
            status_code=401,
            detail="Invalid session token format.",
        )

    # CSRF Protection for state-changing browser cookie requests
    if source == "cookie" and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("Origin")
        has_custom_header = bool(
            request.headers.get("X-Requested-With") or request.headers.get("X-Session-Token")
        )
        # Origin must be whitelisted OR custom header present
        is_allowed_origin = origin and (
            origin in settings.FRONTEND_ORIGINS
            or origin.endswith(".vercel.app")
            or "vercel.app" in origin
        )
        if not is_allowed_origin and not has_custom_header:
            logger.warning(
                f"CSRF protection triggered on {request.method} {request.url.path} from Origin={origin}"
            )
            raise HTTPException(
                status_code=403,
                detail="CSRF validation failed: missing custom client header or unauthorized Origin.",
            )

    # Fetch the portfolio record using server-side client
    try:
        client = get_supabase_client()
        response = (
            client.table("portfolios")
            .select("id, github_username, scan_status, session_token_hash, is_archived, created_at, updated_at")
            .eq("id", str(portfolio_id))
            .execute()
        )
    except Exception as e:
        logger.error(f"Database error during portfolio verification: {type(e).__name__}")
        raise HTTPException(
            status_code=500,
            detail="Internal database error verifying authorization.",
        ) from None

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail=f"Portfolio with ID {portfolio_id} not found.",
        )

    portfolio = response.data[0]

    # Check soft-archival status
    if portfolio.get("is_archived"):
        logger.info(f"Access denied to archived portfolio_id={portfolio_id}")
        raise HTTPException(
            status_code=403,
            detail="Portfolio intake session is archived and read-only.",
        )

    # Check revocation status (None hash indicates revoked session)
    stored_hash = portfolio.get("session_token_hash")
    if not stored_hash:
        logger.info(f"Access denied: revoked session for portfolio_id={portfolio_id}")
        raise HTTPException(
            status_code=401,
            detail="Session has been revoked or expired.",
        )

    # Constant-time comparison between stored hash and incoming token hash
    incoming_hash = hash_session_token(token)
    if not hmac.compare_digest(stored_hash, incoming_hash):
        logger.warning(
            f"Cross-portfolio / invalid token attempt on portfolio_id={portfolio_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Forbidden: session token does not match target portfolio.",
        )

    # Expiry verification against updated_at timestamp
    raw_timestamp = portfolio.get("updated_at") or portfolio.get("created_at")
    if raw_timestamp:
        try:
            # Parse ISO timestamp supporting Z or offset
            ts_clean = raw_timestamp.replace("Z", "+00:00")
            session_time = datetime.fromisoformat(ts_clean)
            now = datetime.now(timezone.utc)
            if now - session_time > timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS):
                logger.info(f"Session expired for portfolio_id={portfolio_id}")
                raise HTTPException(
                    status_code=401,
                    detail="Session has expired. Please restart intake.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error parsing session timestamp: {type(e).__name__}")

    # Return verified portfolio context
    return portfolio


async def get_authenticated_portfolio(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency resolving and authenticating the candidate portfolio
    directly from the session token (cookie or header) without relying on
    client-supplied portfolio ID parameters.
    """
    token, source = extract_session_token(request)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: missing session token.",
            headers={"WWW-Authenticate": "Cookie"},
        )

    if not TOKEN_FORMAT_REGEX.match(token):
        raise HTTPException(
            status_code=401,
            detail="Invalid session token format.",
        )

    # CSRF Protection for state-changing browser cookie requests
    if source == "cookie" and request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("Origin")
        has_custom_header = bool(
            request.headers.get("X-Requested-With") or request.headers.get("X-Session-Token")
        )
        is_allowed_origin = origin and origin in settings.FRONTEND_ORIGINS
        if not is_allowed_origin and not has_custom_header:
            raise HTTPException(
                status_code=403,
                detail="CSRF validation failed: missing custom client header or unauthorized Origin.",
            )

    incoming_hash = hash_session_token(token)

    try:
        client = get_supabase_client()
        res = (
            client.table("portfolios")
            .select("id, github_username, scan_status, session_token_hash, is_archived, created_at, updated_at")
            .eq("session_token_hash", incoming_hash)
            .execute()
        )
    except Exception as e:
        logger.error(f"Database error resolving session token: {type(e).__name__}")
        raise HTTPException(
            status_code=500,
            detail="Internal database error verifying authorization.",
        ) from None

    if not res.data:
        raise HTTPException(
            status_code=401,
            detail="Authentication failed: invalid or expired session token.",
        )

    portfolio = res.data[0]

    if portfolio.get("is_archived"):
        raise HTTPException(
            status_code=403,
            detail="Portfolio intake session is archived and read-only.",
        )

    stored_hash = portfolio.get("session_token_hash")
    if not stored_hash or not hmac.compare_digest(stored_hash, incoming_hash):
        raise HTTPException(
            status_code=401,
            detail="Session has been revoked or expired.",
        )

    raw_timestamp = portfolio.get("updated_at") or portfolio.get("created_at")
    if raw_timestamp:
        try:
            ts_clean = raw_timestamp.replace("Z", "+00:00")
            session_time = datetime.fromisoformat(ts_clean)
            now = datetime.now(timezone.utc)
            if now - session_time > timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS):
                raise HTTPException(
                    status_code=401,
                    detail="Session has expired. Please restart intake.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error parsing session timestamp: {type(e).__name__}")

    return portfolio


def revoke_portfolio_session(portfolio_id: UUID, client: Client) -> None:
    """
    Revokes the active session for a portfolio by nullifying its stored hash.
    Immediate and irreversible without starting a new intake.
    """
    try:
        client.table("portfolios").update({"session_token_hash": None}).eq(
            "id", str(portfolio_id)
        ).execute()
        logger.info(f"Session revoked for portfolio_id={portfolio_id}")
    except Exception as e:
        logger.error(f"Failed to revoke session for portfolio_id={portfolio_id}: {type(e).__name__}")
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke session in database.",
        ) from None
