"""
Memory Manager — short-term and long-term memory with pruning.

Architecture (from AUTONOMOUS_AI_AGENT_ARCHITECTURE.md §4.5):
  - Short-term memory: last N interactions (LangGraph messages)
  - Long-term memory: compressed summaries of older interactions
  - Working memory: current task context (plan, active files, etc.)
  - Relevance retrieval: keyword-based lookup of long-term summaries
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from core.logger import get_logger

logger = get_logger(__name__)


class MemoryEntry(BaseModel):
    """A compressed memory entry from past interactions."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    summary: str
    files_touched: List[str] = Field(default_factory=list)
    commands_run: List[str] = Field(default_factory=list)
    errors_seen: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)


class FixRecord(BaseModel):
    """A record of a code fix attempt, its parameters, and validation outcome."""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    file: str
    issue_category: str
    issue_message: str
    fix_diff: str
    success: bool
    error_message: Optional[str] = None


class WorkingMemory(BaseModel):
    """Current task context — what the agent is actively working on."""
    current_plan: str = ""
    active_files: List[str] = Field(default_factory=list)
    completed_tasks: List[str] = Field(default_factory=list)
    pending_tasks: List[str] = Field(default_factory=list)
    known_errors: List[str] = Field(default_factory=list)
    tech_stack: str = ""
    project_type: str = ""


class MemoryManager:
    """
    Manages agent memory across sessions.

    Memory tiers:
      1. Short-term: LangGraph message history (managed by ContextManager)
      2. Long-term: Compressed summaries stored as MemoryEntry objects
      3. Working: Current task state (plan, files, etc.)
      4. Fix History: Successful and failed fixes for learning
    """

    MAX_LONG_TERM_ENTRIES = 50
    MAX_FIX_RECORDS = 100

    def __init__(self) -> None:
        self.long_term: List[MemoryEntry] = []
        self.working = WorkingMemory()
        self.fix_history: List[FixRecord] = []

    def compress_interactions(self, messages_text: List[str]) -> MemoryEntry:
        """
        Compress a batch of message contents into a single memory entry.
        
        This is called when the ContextManager prunes old messages — instead
        of losing that information entirely, we extract key facts and store
        them in long-term memory.
        """
        files_touched = []
        commands_run = []
        errors_seen = []
        decisions = []

        for text in messages_text:
            # Extract file writes
            files_touched.extend(
                re.findall(r"<write\s+path=['\"]([^'\"]+)['\"]>", text)
            )
            # Also catch "Created file.txt" observations
            files_touched.extend(
                re.findall(r"Created\s+(\S+\.(?:py|ts|tsx|js|jsx|json|html|css|md))", text)
            )

            # Extract commands
            for cmd_match in re.findall(r"<run>(.*?)</run>", text, re.DOTALL):
                cmd = cmd_match.strip()
                if cmd and len(cmd) < 200:
                    commands_run.append(cmd)

            # Extract errors
            for line in text.split("\n"):
                line_stripped = line.strip()
                if any(
                    indicator in line_stripped
                    for indicator in [
                        "Error:", "ERROR", "SyntaxError", "TypeError",
                        "ModuleNotFoundError", "ImportError", "Cannot find",
                        "ENOENT", "exit_code: 1", "failed",
                    ]
                ):
                    if len(line_stripped) < 200:
                        errors_seen.append(line_stripped)

            # Extract high-level decisions (first non-tag line from AI)
            for line in text.split("\n"):
                line_stripped = line.strip()
                if (
                    line_stripped
                    and not line_stripped.startswith("<")
                    and not line_stripped.startswith("Observation")
                    and len(line_stripped) > 20
                    and len(line_stripped) < 200
                ):
                    decisions.append(line_stripped)
                    break

        entry = MemoryEntry(
            summary=self._build_summary(files_touched, commands_run, errors_seen, decisions),
            files_touched=list(set(files_touched)),
            commands_run=commands_run[:10],
            errors_seen=list(set(errors_seen))[:5],
            decisions=decisions[:5],
        )

        self.long_term.append(entry)

        # Prune if too many entries
        if len(self.long_term) > self.MAX_LONG_TERM_ENTRIES:
            self.long_term = self.long_term[-self.MAX_LONG_TERM_ENTRIES:]

        logger.info(
            "memory_compressed",
            files=len(entry.files_touched),
            commands=len(entry.commands_run),
            errors=len(entry.errors_seen),
        )

        return entry

    def update_working_memory(
        self,
        *,
        plan: Optional[str] = None,
        file_written: Optional[str] = None,
        task_completed: Optional[str] = None,
        error_seen: Optional[str] = None,
        tech_stack: Optional[str] = None,
        project_type: Optional[str] = None,
    ) -> None:
        """Update the working memory with new information."""
        if plan is not None:
            self.working.current_plan = plan
        if file_written and file_written not in self.working.active_files:
            self.working.active_files.append(file_written)
        if task_completed:
            self.working.completed_tasks.append(task_completed)
            if task_completed in self.working.pending_tasks:
                self.working.pending_tasks.remove(task_completed)
        if error_seen and error_seen not in self.working.known_errors:
            self.working.known_errors.append(error_seen)
            # Keep only last 10 errors
            self.working.known_errors = self.working.known_errors[-10:]
        if tech_stack:
            self.working.tech_stack = tech_stack
        if project_type:
            self.working.project_type = project_type

    def get_relevant_memory(self, query: str) -> str:
        """
        Retrieve relevant long-term memory for a given query.
        Uses keyword overlap for fast, LLM-free retrieval.
        """
        if not self.long_term:
            return ""

        query_keywords = set(query.lower().split())
        scored_entries = []

        for entry in self.long_term:
            summary_keywords = set(entry.summary.lower().split())
            # Also check file names and error messages
            all_keywords = summary_keywords
            for f in entry.files_touched:
                all_keywords.update(f.lower().replace("/", " ").replace(".", " ").split())
            for e in entry.errors_seen:
                all_keywords.update(e.lower().split())

            overlap = len(query_keywords & all_keywords)
            if overlap > 1:
                scored_entries.append((overlap, entry))

        if not scored_entries:
            return ""

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        top_entries = scored_entries[:3]

        parts = []
        for _, entry in top_entries:
            parts.append(entry.summary)

        return "\n---\n".join(parts)

    def get_working_context(self) -> str:
        """Format working memory as context string for the LLM prompt."""
        parts = []

        if self.working.active_files:
            parts.append(
                f"Files created so far: {', '.join(self.working.active_files[-20:])}"
            )
        if self.working.completed_tasks:
            parts.append(
                f"Completed tasks: {', '.join(self.working.completed_tasks[-10:])}"
            )
        if self.working.known_errors:
            parts.append(
                f"Recent errors: {'; '.join(self.working.known_errors[-3:])}"
            )
        if self.working.tech_stack:
            parts.append(f"Tech stack: {self.working.tech_stack}")
        if self.working.project_type:
            parts.append(f"Project type: {self.working.project_type}")

        return "\n".join(parts) if parts else ""

    def _build_summary(
        self,
        files: List[str],
        commands: List[str],
        errors: List[str],
        decisions: List[str],
    ) -> str:
        """Build a human-readable summary from extracted data."""
        parts = []
        if files:
            unique_files = list(set(files))
            parts.append(f"Created/modified files: {', '.join(unique_files[:10])}")
        if commands:
            parts.append(f"Ran commands: {'; '.join(commands[:5])}")
        if errors:
            parts.append(f"Errors encountered: {'; '.join(errors[:3])}")
        if decisions:
            parts.append(f"Key decisions: {'; '.join(decisions[:3])}")
        return " | ".join(parts) if parts else "General progress."

    def record_fix(
        self,
        file: str,
        issue_category: str,
        issue_message: str,
        fix_diff: str,
        success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """Record a fix attempt in the project memory."""
        record = FixRecord(
            file=file,
            issue_category=issue_category,
            issue_message=issue_message,
            fix_diff=fix_diff,
            success=success,
            error_message=error_message,
        )
        self.fix_history.append(record)

        # Cap fix history to prevent memory bloat
        if len(self.fix_history) > self.MAX_FIX_RECORDS:
            self.fix_history = self.fix_history[-self.MAX_FIX_RECORDS:]

        logger.info(
            "fix_recorded",
            file=file,
            category=issue_category,
            success=success,
            total_records=len(self.fix_history),
        )

    def get_similar_fixes(self, issue_category: str, file_path: str) -> List[FixRecord]:
        """Retrieve past successful fixes for a similar issue category."""
        return [
            rec for rec in self.fix_history
            if rec.success and rec.issue_category == issue_category
        ]

    def get_known_failures(self, issue_category: str, file_path: str) -> List[FixRecord]:
        """Retrieve past FAILED attempts for a similar issue category to avoid repeating them."""
        return [
            rec for rec in self.fix_history
            if not rec.success and rec.issue_category == issue_category
        ]

    def to_dict(self) -> dict:
        """Serialize memory state for debugging / persistence."""
        return {
            "long_term_count": len(self.long_term),
            "working_memory": self.working.model_dump(),
            "long_term_entries": [e.model_dump() for e in self.long_term[-5:]],
            "fix_history": [r.model_dump() for r in self.fix_history[-20:]],
        }
