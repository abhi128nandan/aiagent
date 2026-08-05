"""
Centralized application configuration using Pydantic Settings.

All environment variables are validated at startup. If a required variable
is missing, the server will fail fast with a clear error message instead
of crashing mysteriously at runtime.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # ── Server ──────────────────────────────────────────────────────────
    APP_NAME: str = "AI Agent Builder"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: str = "*"  # comma-separated list

    # ── Database (PostgreSQL) ───────────────────────────────────────────
    POSTGRES_USER: str = "langgraph"
    POSTGRES_PASSWORD: str = "langgraph_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "agent_state"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ───────────────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── LLM Providers ──────────────────────────────────────────────────
    DEFAULT_LLM_PROVIDER: str = "groq"
    DEFAULT_LLM_MODEL: Optional[str] = "groq/llama-3.3-70b-versatile"

    # Multiple Groq keys (comma-separated) for free-tier rate-limit rotation
    GROQ_API_KEYS: Optional[str] = None  # e.g. "gsk_key1,gsk_key2,gsk_key3"
    GROQ_API_KEY: Optional[str] = None   # Single key (backward compat)
    GROQ_API_BASE_URL: str = "https://api.groq.com/openai/v1"

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_BASE_URL: str = "https://api.openai.com/v1"

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_API_BASE_URL: str = "https://api.anthropic.com/v1"
    ANTHROPIC_API_VERSION: str = "2023-06-01"

    GEMINI_API_KEYS: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None

    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── Secrets & Auth ────────────────────────────────────────────────
    SECRETS_FERNET_KEY: Optional[str] = None
    SECRETS_TEST_TIMEOUT: int = 5
    API_AUTH_TOKEN: Optional[str] = None

    # ── Embedding & RAG ────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = ".chroma_db"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RAG_ENABLED: bool = True
    RAG_TOP_K: int = 5

    # ── LangSmith Observability ─────────────────────────────────────────
    LANGSMITH_TRACING: bool = False
    LANGCHAIN_TRACING_V2: bool = False
    LANGSMITH_API_KEY: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "aiagent"
    LANGCHAIN_PROJECT: str = "aiagent"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # ── Context Management ─────────────────────────────────────────────
    DEFAULT_CONTEXT_LIMIT: int = 8192  # Override per-model limits if needed
    CONTEXT_PRUNE_KEEP_LAST: int = 10  # Keep last N messages when pruning

    # ── Docker Sandbox ─────────────────────────────────────────────────
    SANDBOX_IMAGE: str = "agent-sandbox:latest"
    SANDBOX_MEM_LIMIT: str = "512m"
    SANDBOX_CPU_QUOTA: int = 50000
    SANDBOX_TIMEOUT: int = 300  # seconds per command
    SANDBOX_CLEANUP_INTERVAL: int = 3600  # 1 hour

    def get_groq_keys(self) -> list[str]:
        """Parse all available Groq API keys from env vars.

        Priority:
          1. GROQ_API_KEYS (comma-separated list)
          2. GROQ_API_KEY (single key, backward compat)
        """
        keys: list[str] = []

        # Parse comma-separated keys
        if self.GROQ_API_KEYS:
            for k in self.GROQ_API_KEYS.split(","):
                k = k.strip()
                if k:
                    keys.append(k)

        # Add single key if not already in the list
        if self.GROQ_API_KEY:
            single = self.GROQ_API_KEY.strip()
            if single and single not in keys:
                keys.append(single)

        return keys

    def get_gemini_keys(self) -> list[str]:
        """Parse all available Gemini API keys from env vars.

        Priority:
          1. GEMINI_API_KEYS (comma-separated list)
          2. GEMINI_API_KEY (single key, backward compat)
        """
        keys: list[str] = []

        # Parse comma-separated keys
        if self.GEMINI_API_KEYS:
            for k in self.GEMINI_API_KEYS.split(","):
                k = k.strip()
                if k:
                    keys.append(k)

        # Add single key if not already in the list
        if self.GEMINI_API_KEY:
            single = self.GEMINI_API_KEY.strip()
            if single and single not in keys:
                keys.append(single)

        return keys

    def export_to_env(self) -> None:
        """Export LangSmith configuration parameters to os.environ so they are picked up by LangChain/LangGraph."""
        import logging
        logger = logging.getLogger("core.config")

        tracing = (
            self.LANGSMITH_TRACING
            or self.LANGCHAIN_TRACING_V2
            or os.environ.get("LANGSMITH_TRACING", "").lower() in ("true", "1")
            or os.environ.get("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1")
        )
        api_key = (
            self.LANGSMITH_API_KEY
            or self.LANGCHAIN_API_KEY
            or os.environ.get("LANGSMITH_API_KEY")
            or os.environ.get("LANGCHAIN_API_KEY")
        )
        project = self.LANGSMITH_PROJECT or self.LANGCHAIN_PROJECT or "aiagent"
        endpoint = self.LANGSMITH_ENDPOINT or self.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"

        if tracing and api_key:
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGSMITH_API_KEY"] = api_key
            os.environ["LANGCHAIN_API_KEY"] = api_key
            os.environ["LANGSMITH_PROJECT"] = project
            os.environ["LANGCHAIN_PROJECT"] = project
            os.environ["LANGSMITH_ENDPOINT"] = endpoint
            os.environ["LANGCHAIN_ENDPOINT"] = endpoint
            logger.info(f"LangSmith tracing enabled for project: {project}")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
