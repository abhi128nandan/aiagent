"""
AGENTS.md Rules Loader — loads the AIBrain/AGENTS.md knowledge vault
into the agent's system prompt construction.

Loads once per session, and if the document grows large, only injects
the sections relevant to the current task (glob/keyword match against
file paths or task type) rather than the whole file every time.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Set

from core.logger import get_logger

logger = get_logger(__name__)


# ── Session cache ─────────────────────────────────────────────────────────
_session_cache: Dict[str, str] = {}

# Threshold: if AGENTS.md is larger than this, filter to relevant sections
MAX_FULL_INJECTION_CHARS = 1500

# Possible locations for the AGENTS.md vault (relative to backend/)
_AGENTS_MD_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "..", "AIBrain", "AGENTS.md"),
    os.path.join(os.path.dirname(__file__), "..", "..", "AGENTS.md"),
    os.path.join(os.path.dirname(__file__), "..", "AIBrain", "AGENTS.md"),
]


class AgentsRulesLoader:
    """
    Loads and caches AGENTS.md vault content, with intelligent section
    filtering for large files.

    Usage:
        loader = AgentsRulesLoader()
        rules = loader.get_rules(session_id, plan_str, message_history)
    """

    @staticmethod
    def _find_agents_md() -> Optional[str]:
        """Locate the AGENTS.md file on the host filesystem."""
        for candidate in _AGENTS_MD_CANDIDATES:
            resolved = os.path.abspath(candidate)
            if os.path.isfile(resolved):
                return resolved
        return None

    @staticmethod
    def _load_from_disk() -> str:
        """Read AGENTS.md content from disk. Returns empty string if not found."""
        path = AgentsRulesLoader._find_agents_md()
        if not path:
            logger.info("agents_md_not_found", searched=len(_AGENTS_MD_CANDIDATES))
            return ""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info("agents_md_loaded", path=path, chars=len(content))
            return content
        except Exception as e:
            logger.warning("agents_md_read_error", path=path, error=str(e))
            return ""

    @staticmethod
    def load(session_id: str) -> str:
        """
        Load AGENTS.md content, cached per session.
        Returns the full raw content (filtering happens in get_relevant_sections).
        """
        if session_id in _session_cache:
            return _session_cache[session_id]

        content = AgentsRulesLoader._load_from_disk()
        _session_cache[session_id] = content
        return content

    @staticmethod
    def clear_cache(session_id: str = "") -> None:
        """Clear the cache for a specific session or all sessions."""
        if session_id:
            _session_cache.pop(session_id, None)
        else:
            _session_cache.clear()

    @staticmethod
    def _split_sections(content: str) -> List[dict]:
        """
        Split markdown content into sections based on ## headers.

        Returns list of {heading: str, body: str, full: str} dicts.
        """
        sections = []
        # Split on ## headers (keep the header with the section)
        parts = re.split(r'^(#{1,3}\s+.+)$', content, flags=re.MULTILINE)

        current_heading = ""
        current_body = ""

        for part in parts:
            if re.match(r'^#{1,3}\s+', part):
                # Save previous section
                if current_heading or current_body.strip():
                    sections.append({
                        "heading": current_heading,
                        "body": current_body.strip(),
                        "full": f"{current_heading}\n{current_body.strip()}" if current_heading else current_body.strip(),
                    })
                current_heading = part.strip()
                current_body = ""
            else:
                current_body += part

        # Save last section
        if current_heading or current_body.strip():
            sections.append({
                "heading": current_heading,
                "body": current_body.strip(),
                "full": f"{current_heading}\n{current_body.strip()}" if current_heading else current_body.strip(),
            })

        return sections

    @staticmethod
    def _extract_keywords(text: str) -> Set[str]:
        """Extract lowercase keywords from text for matching."""
        # Extract words, file extensions, path components
        words = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text.lower()))
        # Also extract file extensions
        extensions = set(re.findall(r'\.\w+', text.lower()))
        # Path fragments
        paths = set(re.findall(r'[\w\-]+/[\w\-./]+', text.lower()))
        return words | extensions | {p.split('/')[0] for p in paths}

    @staticmethod
    def get_relevant_sections(
        full_text: str,
        file_paths: List[str],
        task_description: str,
        max_chars: int = MAX_FULL_INJECTION_CHARS,
    ) -> str:
        """
        If the document exceeds max_chars, filter to the sections most
        relevant to the current task and file paths.

        Args:
            full_text: Complete AGENTS.md content
            file_paths: List of file paths from the plan steps
            task_description: Current task or SRS text (for keyword matching)
            max_chars: Maximum characters to return

        Returns:
            Filtered (or full) document text
        """
        if not full_text:
            return ""

        # Small enough → return the whole thing
        if len(full_text) <= max_chars:
            return full_text

        sections = AgentsRulesLoader._split_sections(full_text)
        if not sections:
            return full_text[:max_chars]

        # Build keyword set from task context
        context_text = task_description + " " + " ".join(file_paths)
        context_keywords = AgentsRulesLoader._extract_keywords(context_text)

        # Score each section by keyword overlap
        scored = []
        for section in sections:
            section_keywords = AgentsRulesLoader._extract_keywords(
                section["heading"] + " " + section["body"]
            )
            overlap = len(context_keywords & section_keywords)
            scored.append((overlap, section))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Always include the first section (usually project summary / intro)
        result_parts = []
        total_chars = 0

        # Include header/intro section first
        if scored:
            first = scored[0][1]
            result_parts.append(first["full"])
            total_chars += len(first["full"])

        # Add remaining scored sections that fit
        for score, section in scored[1:]:
            if score == 0:
                continue  # Skip completely irrelevant sections
            section_text = section["full"]
            if total_chars + len(section_text) + 2 > max_chars:
                continue
            result_parts.append(section_text)
            total_chars += len(section_text) + 2

        return "\n\n".join(result_parts)

    @staticmethod
    def get_rules(
        session_id: str,
        plan_str: str = "",
        message_history: list = None,
    ) -> str:
        """
        Public API: Load, filter, and return formatted AGENTS.md rules.

        Args:
            session_id: Current session ID (for caching)
            plan_str: JSON plan string (for file path extraction)
            message_history: Recent messages (for keyword extraction)

        Returns:
            Formatted rules string ready for prompt injection, or empty string.
        """
        import json

        full_text = AgentsRulesLoader.load(session_id)
        if not full_text:
            return ""

        # Extract file paths from plan
        file_paths = []
        try:
            plan = json.loads(plan_str)
            for step in plan.get("steps", []):
                if isinstance(step, dict):
                    fp = step.get("file", step.get("file_path", ""))
                    if fp:
                        file_paths.append(fp)
        except (json.JSONDecodeError, TypeError):
            pass

        # Extract task description from recent messages
        task_description = ""
        if message_history:
            for msg in message_history[-3:]:
                if hasattr(msg, "content") and isinstance(msg.content, str):
                    task_description += " " + msg.content

        relevant = AgentsRulesLoader.get_relevant_sections(
            full_text, file_paths, task_description
        )

        if not relevant:
            return ""

        return f"## Project Knowledge Vault (AGENTS.md)\n{relevant}"
