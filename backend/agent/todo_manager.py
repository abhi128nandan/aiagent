"""
Todo Manager — Structured plan state persistence.

Formalizes Planner/Detail Planner output into an explicit todo structure:
  {id, content, status: pending|in_progress|completed, file_path, action}

Persists to /workspace/.myaiagent/todos.json so it survives across sessions
and is human-editable before execution. The Judge can append new todos
mid-run without discarding completed ones.

Backward compatible: also generates the existing tasks_todo.md markdown format.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from core.logger import get_logger

logger = get_logger(__name__)


# ── Models ────────────────────────────────────────────────────────────────

class TodoItem(BaseModel):
    """Single actionable item derived from a plan step."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = Field(description="Description of the task")
    status: Literal["pending", "in_progress", "completed"] = "pending"
    file_path: str = Field(default="", description="File this todo targets")
    action: str = Field(default="modify", description="create | modify | run")


class TodoList(BaseModel):
    """Persistent todo list for a planning session."""
    project: str = ""
    items: List[TodoItem] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Manager ───────────────────────────────────────────────────────────────

# Module-level cache: session_id → TodoList
_todo_cache: Dict[str, TodoList] = {}

TODOS_CONTAINER_PATH = "/workspace/.myaiagent/todos.json"
TODOS_DIR = "/workspace/.myaiagent"


class TodoManager:
    """
    Manages the lifecycle of structured todo items.

    Usage:
        mgr = TodoManager(session_id="abc")
        mgr.sync_from_plan(plan_json_str)
        mgr.update_status("src/App.jsx", "in_progress")
        mgr.append_todos([{"content": "Add error handler", "file_path": "src/error.jsx"}])
        await mgr.save(runtime)
    """

    def __init__(self, session_id: str = ""):
        self.session_id = session_id
        self._todo_list: TodoList = _todo_cache.get(session_id, TodoList())

    @property
    def todo_list(self) -> TodoList:
        return self._todo_list

    # ── Sync from plan ─────────────────────────────────────────────────

    def sync_from_plan(self, plan_json: str) -> TodoList:
        """
        Parse plan steps into TodoItems.

        If a TodoList already exists (from a prior run), preserves completed
        items and only adds/updates pending ones. This is the key difference
        from the existing update_tasks_todo() which regenerates everything.
        """
        try:
            plan = json.loads(plan_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("todo_sync_invalid_plan", session_id=self.session_id)
            return self._todo_list

        steps = plan.get("steps", [])
        project_name = plan.get("project", "")

        # Build lookup of existing items by file_path for merge
        existing_by_path: Dict[str, TodoItem] = {
            item.file_path: item
            for item in self._todo_list.items
            if item.file_path
        }

        new_items: List[TodoItem] = []
        seen_paths: set = set()

        for step in steps:
            if not isinstance(step, dict):
                continue

            file_path = step.get("file", step.get("file_path", ""))
            if not file_path:
                continue

            description = step.get("description", step.get("content", ""))
            action = step.get("action", "modify").lower()

            # If this file already has a completed todo, preserve it
            if file_path in existing_by_path:
                existing = existing_by_path[file_path]
                if existing.status == "completed":
                    new_items.append(existing)
                    seen_paths.add(file_path)
                    continue

            # Create or update the todo item
            item_id = existing_by_path[file_path].id if file_path in existing_by_path else str(uuid.uuid4())[:8]
            new_items.append(TodoItem(
                id=item_id,
                content=description,
                status="pending",
                file_path=file_path,
                action=action,
            ))
            seen_paths.add(file_path)

        # Preserve any completed items whose file_path wasn't in the new plan
        for item in self._todo_list.items:
            if item.file_path not in seen_paths and item.status == "completed":
                new_items.append(item)

        self._todo_list = TodoList(
            project=project_name or self._todo_list.project,
            items=new_items,
            created_at=self._todo_list.created_at,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        _todo_cache[self.session_id] = self._todo_list
        logger.info(
            "todo_synced_from_plan",
            session_id=self.session_id,
            total=len(new_items),
            completed=sum(1 for i in new_items if i.status == "completed"),
        )
        return self._todo_list

    # ── Status updates ─────────────────────────────────────────────────

    def update_status(self, file_path: str, new_status: Literal["pending", "in_progress", "completed"]) -> bool:
        """Update the status of a todo item by file_path. Returns True if found."""
        normalized = file_path.lstrip("/")
        for item in self._todo_list.items:
            if item.file_path.lstrip("/") == normalized:
                item.status = new_status
                self._todo_list.updated_at = datetime.now(timezone.utc).isoformat()
                _todo_cache[self.session_id] = self._todo_list
                return True
        return False

    def mark_file_completed(self, file_path: str) -> bool:
        """Convenience: mark a file's todo as completed."""
        return self.update_status(file_path, "completed")

    def mark_file_in_progress(self, file_path: str) -> bool:
        """Convenience: mark a file's todo as in_progress."""
        return self.update_status(file_path, "in_progress")

    # ── Append (Judge mid-run additions) ───────────────────────────────

    def append_todos(self, new_items: List[dict]) -> int:
        """
        Append new todo items discovered mid-run (e.g., by the Judge).
        Does NOT touch completed items.

        Args:
            new_items: List of dicts with at least 'content', optionally
                       'file_path' and 'action'.

        Returns:
            Number of items actually appended (skips duplicates by file_path).
        """
        existing_paths = {item.file_path for item in self._todo_list.items if item.file_path}
        appended = 0

        for raw in new_items:
            if not isinstance(raw, dict):
                continue

            content = raw.get("content", raw.get("description", ""))
            file_path = raw.get("file_path", raw.get("file", ""))
            action = raw.get("action", "create")

            if not content:
                continue

            # Skip if we already have a todo for this file
            if file_path and file_path in existing_paths:
                continue

            self._todo_list.items.append(TodoItem(
                content=content,
                file_path=file_path,
                action=action,
                status="pending",
            ))
            if file_path:
                existing_paths.add(file_path)
            appended += 1

        if appended:
            self._todo_list.updated_at = datetime.now(timezone.utc).isoformat()
            _todo_cache[self.session_id] = self._todo_list
            logger.info(
                "todo_items_appended",
                session_id=self.session_id,
                appended=appended,
                total=len(self._todo_list.items),
            )

        return appended

    # ── Persistence (Docker container I/O) ─────────────────────────────

    async def save(self, runtime) -> bool:
        """
        Persist the todo list to /workspace/.myaiagent/todos.json inside the
        Docker container. Also writes the backward-compat tasks_todo.md.

        Args:
            runtime: DockerRuntime instance with .container and .execute()

        Returns:
            True if save succeeded.
        """
        import asyncio
        import io
        import tarfile

        try:
            todo_json = self._todo_list.model_dump_json(indent=2)
            todo_md = self.to_markdown()

            loop = asyncio.get_event_loop()

            def _write_files():
                # Ensure directory exists
                runtime.container.exec_run(f"mkdir -p {TODOS_DIR}")

                tar_stream = io.BytesIO()
                with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                    # Write JSON
                    json_bytes = todo_json.encode("utf-8")
                    json_info = tarfile.TarInfo(name=".myaiagent/todos.json")
                    json_info.size = len(json_bytes)
                    json_info.mtime = int(time.time())
                    tar.addfile(json_info, io.BytesIO(json_bytes))

                    # Write markdown (backward compat)
                    md_bytes = todo_md.encode("utf-8")
                    md_info = tarfile.TarInfo(name="tasks_todo.md")
                    md_info.size = len(md_bytes)
                    md_info.mtime = int(time.time())
                    tar.addfile(md_info, io.BytesIO(md_bytes))

                tar_stream.seek(0)
                runtime.container.put_archive("/workspace", tar_stream)

            await loop.run_in_executor(None, _write_files)
            logger.info("todo_saved", session_id=self.session_id, items=len(self._todo_list.items))
            return True

        except Exception as e:
            logger.warning("todo_save_failed", session_id=self.session_id, error=str(e))
            return False

    async def load(self, runtime) -> bool:
        """
        Load the todo list from /workspace/.myaiagent/todos.json.

        Returns:
            True if load succeeded; False if file doesn't exist or is corrupted.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()

            def _read_file():
                result = runtime.container.exec_run(f"cat {TODOS_CONTAINER_PATH}")
                if result.exit_code != 0:
                    return None
                return result.output.decode("utf-8", errors="replace").strip()

            content = await loop.run_in_executor(None, _read_file)
            if not content:
                return False

            self._todo_list = TodoList.model_validate_json(content)
            _todo_cache[self.session_id] = self._todo_list
            logger.info(
                "todo_loaded",
                session_id=self.session_id,
                items=len(self._todo_list.items),
                completed=sum(1 for i in self._todo_list.items if i.status == "completed"),
            )
            return True

        except Exception as e:
            logger.warning("todo_load_failed", session_id=self.session_id, error=str(e))
            return False

    # ── Markdown rendering (backward compat) ───────────────────────────

    def to_markdown(self) -> str:
        """
        Generate the same markdown format as the existing update_tasks_todo()
        function for backward compatibility with the frontend.
        """
        tl = self._todo_list
        lines = [
            f"# Project: {tl.project}\n",
            "## Tasks Checklist\n",
        ]

        for item in tl.items:
            if not item.file_path:
                continue

            if item.status == "completed":
                icon = "[x]"
            elif item.status == "in_progress":
                icon = "[/]"
            else:
                icon = "[ ]"

            action_upper = item.action.upper()
            lines.append(f"- {icon} **{action_upper}** `{item.file_path}`")
            lines.append(f"  *Description:* {item.content}\n")

        return "\n".join(lines)
