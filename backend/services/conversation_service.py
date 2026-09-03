"""Conversation lifecycle management."""
from __future__ import annotations

import os
import uuid
from typing import Any, Optional

import psycopg

from core.config import get_settings
from core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


_memory_conversations: dict[str, dict[str, Any]] = {}
_db_unavailable: bool = os.environ.get("USE_MEMORY_CHECKPOINTER", "false").lower() in ("true", "1", "yes")

class ConversationService:
    """Stores conversation lifecycle metadata in PostgreSQL with in-memory fallback."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or settings.database_url

    @property
    def _use_memory(self) -> bool:
        return _db_unavailable

    @_use_memory.setter
    def _use_memory(self, val: bool) -> None:
        global _db_unavailable
        _db_unavailable = val

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def create_conversation(self) -> dict[str, Any]:
        conversation_id = str(uuid.uuid4())
        c_data = {
            "id": conversation_id,
            "status": "active",
            "created_at": None,
            "updated_at": None,
        }
        if self._use_memory:
            _memory_conversations[conversation_id] = c_data
            return c_data

        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                conn.execute(
                    """
                    INSERT INTO conversations (id, status)
                    VALUES (%s, %s)
                    """,
                    (conversation_id, "active"),
                )
                conn.commit()
            return self.get_conversation(conversation_id) or c_data
        except Exception as e:
            logger.warning("conversation_db_fallback", reason=str(e))
            self._use_memory = True
            _memory_conversations[conversation_id] = c_data
            return c_data

    def list_conversations(self) -> list[dict[str, Any]]:
        if self._use_memory:
            return list(_memory_conversations.values())
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                rows = conn.execute(
                    """
                    SELECT id, status, created_at, updated_at
                    FROM conversations
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
            return [self._row_to_conversation(row) for row in rows]
        except Exception:
            self._use_memory = True
            return list(_memory_conversations.values())

    def get_conversation(self, conversation_id: str) -> Optional[dict[str, Any]]:
        if self._use_memory:
            return _memory_conversations.get(conversation_id)
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                row = conn.execute(
                    """
                    SELECT id, status, created_at, updated_at
                    FROM conversations
                    WHERE id = %s
                    """,
                    (conversation_id,),
                ).fetchone()
            return self._row_to_conversation(row) if row else None
        except Exception:
            self._use_memory = True
            return _memory_conversations.get(conversation_id)

    def mark_active(self, conversation_id: str) -> Optional[dict[str, Any]]:
        return self._update_status(conversation_id, "active")

    def pause_conversation(self, conversation_id: str) -> Optional[dict[str, Any]]:
        return self._update_status(conversation_id, "paused")

    def resume_conversation(self, conversation_id: str) -> Optional[dict[str, Any]]:
        return self._update_status(conversation_id, "active")

    def delete_conversation(self, conversation_id: str) -> bool:
        if self._use_memory:
            return _memory_conversations.pop(conversation_id, None) is not None
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                result = conn.execute(
                    "DELETE FROM conversations WHERE id = %s",
                    (conversation_id,),
                )
                conn.commit()
            return result.rowcount > 0
        except Exception:
            self._use_memory = True
            return _memory_conversations.pop(conversation_id, None) is not None

    def _update_status(self, conversation_id: str, status: str) -> Optional[dict[str, Any]]:
        if self._use_memory:
            if conversation_id in _memory_conversations:
                _memory_conversations[conversation_id]["status"] = status
            return _memory_conversations.get(conversation_id)
        try:
            with self._connect() as conn:
                self._ensure_table(conn)
                conn.execute(
                    """
                    UPDATE conversations
                    SET status = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (status, conversation_id),
                )
                conn.commit()
            return self.get_conversation(conversation_id)
        except Exception:
            self._use_memory = True
            if conversation_id in _memory_conversations:
                _memory_conversations[conversation_id]["status"] = status
            return _memory_conversations.get(conversation_id)

    def _ensure_table(self, conn: psycopg.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id UUID PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        conn.commit()

    def _row_to_conversation(self, row: tuple) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "status": row[1],
            "created_at": row[2].isoformat() if row[2] else None,
            "updated_at": row[3].isoformat() if row[3] else None,
        }

    def _ensure_events_table(self, conn: psycopg.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_events (
                id SERIAL PRIMARY KEY,
                session_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                payload JSONB NOT NULL,
                seq INT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        conn.commit()

    def add_event(self, session_id: str, event_type: str, payload: dict, seq: int) -> None:
        import json
        with self._connect() as conn:
            self._ensure_events_table(conn)
            # The session may come from a client that reconnected after a DB
            # reset (or generated its own UUID) — create the conversation row
            # if missing so the FK on session_events never rejects the event.
            conn.execute(
                """
                INSERT INTO conversations (id, status)
                VALUES (%s, 'active')
                ON CONFLICT (id) DO NOTHING
                """,
                (session_id,),
            )
            conn.execute(
                """
                INSERT INTO session_events (session_id, event_type, payload, seq)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, event_type, json.dumps(payload), seq),
            )
            conn.commit()

    def get_events(self, session_id: str) -> list[dict]:
        with self._connect() as conn:
            self._ensure_events_table(conn)
            rows = conn.execute(
                """
                SELECT payload, seq FROM session_events
                WHERE session_id = %s
                ORDER BY seq ASC
                """,
                (session_id,),
            ).fetchall()
        
        events = []
        for row in rows:
            payload = row[0]
            if isinstance(payload, str):
                import json
                payload = json.loads(payload)
            payload["seq"] = row[1]
            events.append(payload)
        return events

