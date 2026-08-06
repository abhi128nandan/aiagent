"""Settings and LLM profile management service."""
from __future__ import annotations

import uuid
from typing import Any, Optional

import psycopg
from psycopg.types.json import Json

from core.config import get_settings
from core.logger import get_logger
from models.llm_profile import LLMProfile, LLMProfileCreate, LLMProfileUpdate

settings = get_settings()
logger = get_logger(__name__)


DEFAULT_SETTINGS: dict[str, Any] = {
    "default_llm_profile": None,
    "sandbox_timeout": settings.SANDBOX_TIMEOUT,
    "max_retries": 5,
    "debug_mode": settings.DEBUG,
    "role_profile_planner": None,
    "role_profile_backend": None,
    "role_profile_frontend": None,
    "role_profile_validator": None,
}

ALLOWED_SETTINGS: dict[str, type | tuple[type, ...]] = {
    "default_llm_profile": (str, type(None)),
    "sandbox_timeout": int,
    "max_retries": int,
    "debug_mode": bool,
    "role_profile_planner": (str, type(None)),
    "role_profile_backend": (str, type(None)),
    "role_profile_frontend": (str, type(None)),
    "role_profile_validator": (str, type(None)),
}


class SettingsService:
    """Provides CRUD for LLM profiles and user settings."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or settings.database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def _ensure_tables(self, conn: psycopg.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_profiles (
                id UUID PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                temperature DOUBLE PRECISION NOT NULL,
                max_tokens INTEGER,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        conn.commit()

    def _row_to_profile(self, row: tuple[Any, ...]) -> LLMProfile:
        (
            profile_id,
            provider,
            model,
            temperature,
            max_tokens,
            is_default,
            created_at,
            updated_at,
        ) = row
        return LLMProfile(
            id=str(profile_id),
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            is_default=is_default,
            created_at=created_at.isoformat() if created_at else None,
            updated_at=updated_at.isoformat() if updated_at else None,
        )

    def _validate_setting(self, key: str, value: Any) -> None:
        if key not in ALLOWED_SETTINGS:
            raise ValueError("Unknown setting")
        expected = ALLOWED_SETTINGS[key]
        if not isinstance(value, expected):
            raise ValueError("Invalid setting type")

    # ---- LLM Profiles ----

    def create_profile(self, payload: LLMProfileCreate) -> LLMProfile:
        profile_id = uuid.uuid4()

        with self._connect() as conn:
            self._ensure_tables(conn)
            if payload.is_default:
                conn.execute("UPDATE llm_profiles SET is_default = FALSE")
            conn.execute(
                """
                INSERT INTO llm_profiles (id, provider, model, temperature, max_tokens, is_default)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    profile_id,
                    payload.provider,
                    payload.model,
                    payload.temperature,
                    payload.max_tokens,
                    payload.is_default,
                ),
            )
            conn.commit()

        profile = self.get_profile(str(profile_id))
        if profile and payload.is_default:
            self.set_default_profile(profile.id)
        return profile

    def list_profiles(self) -> list[LLMProfile]:
        with self._connect() as conn:
            self._ensure_tables(conn)
            rows = conn.execute(
                """
                SELECT id, provider, model, temperature, max_tokens, is_default, created_at, updated_at
                FROM llm_profiles
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get_profile(self, profile_id: str) -> Optional[LLMProfile]:
        with self._connect() as conn:
            self._ensure_tables(conn)
            row = conn.execute(
                """
                SELECT id, provider, model, temperature, max_tokens, is_default, created_at, updated_at
                FROM llm_profiles
                WHERE id = %s
                """,
                (profile_id,),
            ).fetchone()
        return self._row_to_profile(row) if row else None

    def update_profile(self, profile_id: str, payload: LLMProfileUpdate) -> Optional[LLMProfile]:
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return self.get_profile(profile_id)

        if fields.get("is_default"):
            self.set_default_profile(profile_id)
            fields.pop("is_default", None)

        if fields:
            assignments = ", ".join(f"{key} = %s" for key in fields)
            values = list(fields.values())
            values.append(profile_id)
            with self._connect() as conn:
                self._ensure_tables(conn)
                conn.execute(
                    f"UPDATE llm_profiles SET {assignments}, updated_at = NOW() WHERE id = %s",
                    values,
                )
                conn.commit()

        return self.get_profile(profile_id)

    def delete_profile(self, profile_id: str) -> bool:
        with self._connect() as conn:
            self._ensure_tables(conn)
            row = conn.execute(
                "SELECT is_default FROM llm_profiles WHERE id = %s",
                (profile_id,),
            ).fetchone()
            result = conn.execute(
                "DELETE FROM llm_profiles WHERE id = %s",
                (profile_id,),
            )
            conn.commit()

        if row and row[0]:
            self._clear_default_profile()
        return result.rowcount > 0

    def set_default_profile(self, profile_id: str) -> LLMProfile:
        with self._connect() as conn:
            self._ensure_tables(conn)
            row = conn.execute(
                "SELECT id FROM llm_profiles WHERE id = %s",
                (profile_id,),
            ).fetchone()
            if not row:
                raise ValueError("Profile not found")

            conn.execute("UPDATE llm_profiles SET is_default = FALSE")
            conn.execute(
                "UPDATE llm_profiles SET is_default = TRUE, updated_at = NOW() WHERE id = %s",
                (profile_id,),
            )
            conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES ('default_llm_profile', %s)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (Json(profile_id),),
            )
            conn.commit()

        profile = self.get_profile(profile_id)
        if profile is None:
            raise ValueError("Profile not found")
        return profile

    def get_default_profile(self) -> Optional[LLMProfile]:
        profile_id = None
        with self._connect() as conn:
            self._ensure_tables(conn)
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'default_llm_profile'"
            ).fetchone()
            if row:
                profile_id = row[0]

        if profile_id:
            profile = self.get_profile(str(profile_id))
            if profile:
                return profile

        with self._connect() as conn:
            self._ensure_tables(conn)
            row = conn.execute(
                """
                SELECT id, provider, model, temperature, max_tokens, is_default, created_at, updated_at
                FROM llm_profiles WHERE is_default = TRUE LIMIT 1
                """
            ).fetchone()
        return self._row_to_profile(row) if row else None

    # ---- Settings ----

    def get_settings(self) -> dict[str, Any]:
        current = dict(DEFAULT_SETTINGS)
        with self._connect() as conn:
            self._ensure_tables(conn)
            rows = conn.execute(
                "SELECT key, value FROM app_settings"
            ).fetchall()

        for key, value in rows:
            if key in current:
                current[key] = value
        return current

    def update_setting(self, key: str, value: Any) -> dict[str, Any]:
        self._validate_setting(key, value)

        if key == "default_llm_profile":
            if value is None:
                self._clear_default_profile()
                return {key: None}
            profile = self.set_default_profile(str(value))
            return {key: profile.id}

        with self._connect() as conn:
            self._ensure_tables(conn)
            conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (key, Json(value)),
            )
            conn.commit()
        return {key: value}

    def reset_settings(self) -> dict[str, Any]:
        with self._connect() as conn:
            self._ensure_tables(conn)
            conn.execute("DELETE FROM app_settings")
            conn.execute("UPDATE llm_profiles SET is_default = FALSE")
            conn.commit()
        return dict(DEFAULT_SETTINGS)

    def _clear_default_profile(self) -> None:
        with self._connect() as conn:
            self._ensure_tables(conn)
            conn.execute("UPDATE llm_profiles SET is_default = FALSE")
            conn.execute("DELETE FROM app_settings WHERE key = 'default_llm_profile'")
            conn.commit()
