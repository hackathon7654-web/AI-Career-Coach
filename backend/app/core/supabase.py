"""
ProofPath AI — Server-Side Supabase Client Provider
Provides secure, centralized access to Supabase via server-side service-role client.
Never exposes credentials to the frontend, logs, or exception messages.
"""
import logging
from typing import Optional
from supabase import Client, create_client
from app.core.config import settings

logger = logging.getLogger("proofpath_ai.supabase")


class SupabaseConfigurationError(RuntimeError):
    """Raised when server-side Supabase credentials are missing or invalid."""
    pass


# Internal singleton client reference
_client_instance: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Returns a cached server-side Supabase client initialized with service_role credentials.
    Fails closed if server-side configuration is missing.
    Can be overridden via FastAPI dependency_overrides in testing environments.
    """
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise SupabaseConfigurationError(
            "Supabase server configuration is missing. "
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured in environment."
        )

    try:
        # Create server-side service_role client (bypasses RLS strictly on the backend)
        _client_instance = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        return _client_instance
    except Exception as e:
        # Fail closed without leaking secret values or full connection strings
        error_type = type(e).__name__
        logger.error(f"Failed to initialize server-side Supabase client: {error_type}")
        raise SupabaseConfigurationError(
            f"Failed to initialize Supabase client: {error_type}"
        ) from None


def override_supabase_client(client: Optional[Client]) -> None:
    """
    Overrides the internal client instance.
    Used exclusively in testing to inject mock clients without live network calls.
    """
    global _client_instance
    _client_instance = client


def reset_supabase_client() -> None:
    """Resets the cached Supabase client instance."""
    global _client_instance
    _client_instance = None
