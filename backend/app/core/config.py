from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings for ProofPath AI.
    Loads from environment variables and optional .env file.
    Provides safe defaults for local development.
    """
    # Application Information
    APP_NAME: str = "ProofPath AI API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # Server Configuration
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # CORS Whitelist (Local frontend Vite dev server)
    FRONTEND_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Candidate Session Configuration (Phase 3D)
    SESSION_COOKIE_NAME: str = "proofpath_session"
    SESSION_MAX_AGE_SECONDS: int = 604800  # 7 days
    SESSION_COOKIE_SECURE: Optional[bool] = None  # None = auto (False in dev, True in prod)
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_COOKIE_PATH: str = "/"
    SESSION_SECRET: str = "proofpath-secure-intake-session-secret-2026"

    # GitHub REST Integration & Limits (Phase 3D-2)
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    GITHUB_TIMEOUT_SECONDS: float = 10.0
    GITHUB_MAX_PAGES: int = 5
    GITHUB_PER_PAGE_MAX: int = 50

    # Bounded Repository Scanning & Evidence Limits (Phase 3D-3)
    MAX_FILES_PER_REPO: int = 50
    MAX_FILE_SIZE_BYTES: int = 512000  # 500 KB limit per file
    MAX_TOTAL_REPO_BYTES: int = 10485760  # 10 MB limit per repo
    SCAN_TIMEOUT_SECONDS: float = 30.0  # 30-second bounded ceiling per repository
    MAX_SELECTED_REPOSITORIES: int = 10  # Maximum repos candidate may select simultaneously

    # Future Phase 3C+ placeholders (Optional, default None so app boots without them)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    DATABASE_URL: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gemini-1.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
