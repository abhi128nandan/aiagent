"""
Tests for AgentsRulesLoader — AGENTS.md knowledge vault loading.

Verifies:
- Once-per-session caching
- Section filtering for large documents
- Small documents returned whole
- Missing AGENTS.md graceful fallback
"""
import os
import pytest
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.rules_loader import AgentsRulesLoader, _session_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the session cache before each test."""
    _session_cache.clear()
    yield
    _session_cache.clear()


SMALL_AGENTS_MD = """# Project Rules

## HARD RULES
1. Read CURRENT_STATE.md before answering any project question
2. Never invent facts not present in source files

## TASK PROTOCOL
Before executing any task:
- State what you understand the goal to be
- State which files you will read and modify
"""

LARGE_AGENTS_MD = """# AI AGENT CONTEXT — myaiagent Project

## PROJECT SUMMARY
Name: myaiagent (Antigravity AI-powered IDE)
Stack: FastAPI + LangGraph + Groq API + React frontend
Goal: AI coding assistant with Docker sandboxing, bidirectional terminal streaming

## BACKEND RULES
- Use FastAPI for all API endpoints
- Follow PEP-8 strictly
- All database models must use SQLAlchemy ORM
- Never commit secrets or API keys to repository
- Implement proper error handling with try-except blocks

## FRONTEND RULES
- Use React functional components with hooks
- Styling via CSS modules or styled-components
- All components must have PropTypes or TypeScript interfaces
- Use React Router for navigation
- State management via Context API or Zustand

## TESTING RULES
- Write unit tests for all utility functions
- Integration tests for API endpoints
- Use pytest for backend, Jest for frontend
- Minimum 80% code coverage target

## DEPLOYMENT RULES
- Docker containers for all services
- CI/CD via GitHub Actions
- Environment variables for configuration
- Health check endpoints required

## DATABASE RULES
- PostgreSQL for production
- SQLite for development
- Alembic for migrations
- Never use raw SQL queries

## SECURITY RULES
- JWT authentication for all protected endpoints
- Rate limiting on public APIs
- Input validation on all user inputs
- CORS configuration required
""" + ("x " * 500)  # Pad to exceed 1500 chars


def test_load_caches_per_session():
    """Second call for same session_id returns cached content without disk I/O."""
    with patch.object(AgentsRulesLoader, '_load_from_disk', return_value=SMALL_AGENTS_MD) as mock_load:
        # First call — hits disk
        content1 = AgentsRulesLoader.load("session-cache-test")
        assert mock_load.call_count == 1

        # Second call — cached
        content2 = AgentsRulesLoader.load("session-cache-test")
        assert mock_load.call_count == 1  # Still 1 — didn't hit disk again

        assert content1 == content2
        assert content1 == SMALL_AGENTS_MD


def test_different_sessions_independent():
    """Different sessions get independent cache entries."""
    with patch.object(AgentsRulesLoader, '_load_from_disk', return_value=SMALL_AGENTS_MD):
        AgentsRulesLoader.load("session-a")
        AgentsRulesLoader.load("session-b")

        assert "session-a" in _session_cache
        assert "session-b" in _session_cache


def test_small_doc_returns_whole():
    """Document <1500 chars returns entire content."""
    result = AgentsRulesLoader.get_relevant_sections(
        SMALL_AGENTS_MD,
        file_paths=["src/App.jsx"],
        task_description="Build a React app",
        max_chars=1500,
    )
    assert result == SMALL_AGENTS_MD


def test_section_filtering_large_doc():
    """Document >1500 chars triggers section filtering; only relevant sections included."""
    result = AgentsRulesLoader.get_relevant_sections(
        LARGE_AGENTS_MD,
        file_paths=["src/App.jsx", "src/components/Header.tsx"],
        task_description="Build frontend React components with hooks",
        max_chars=1500,
    )

    # Should include frontend-relevant sections
    assert "FRONTEND" in result or "React" in result
    # Should NOT include the entire massive document
    assert len(result) <= 1500


def test_section_filtering_backend_focus():
    """Backend-focused task should prioritize backend sections."""
    result = AgentsRulesLoader.get_relevant_sections(
        LARGE_AGENTS_MD,
        file_paths=["app.py", "models.py", "routes/api.py"],
        task_description="Create FastAPI backend with SQLAlchemy models",
        max_chars=1500,
    )

    # Should include backend-relevant sections
    assert "BACKEND" in result or "FastAPI" in result or "SQLAlchemy" in result


def test_missing_agents_md_graceful():
    """Returns empty string if AGENTS.md doesn't exist."""
    with patch.object(AgentsRulesLoader, '_find_agents_md', return_value=None):
        result = AgentsRulesLoader.load("session-missing")
        assert result == ""


def test_get_rules_returns_formatted():
    """get_rules returns formatted string with header."""
    with patch.object(AgentsRulesLoader, '_load_from_disk', return_value=SMALL_AGENTS_MD):
        result = AgentsRulesLoader.get_rules(
            session_id="session-rules",
            plan_str='{"steps": [{"file": "main.py"}]}',
            message_history=[],
        )
        assert "## Project Knowledge Vault (AGENTS.md)" in result
        assert "HARD RULES" in result


def test_get_rules_empty_when_no_file():
    """get_rules returns empty string when AGENTS.md is missing."""
    with patch.object(AgentsRulesLoader, '_load_from_disk', return_value=""):
        result = AgentsRulesLoader.get_rules(
            session_id="session-empty",
            plan_str='{}',
        )
        assert result == ""


def test_get_rules_extracts_file_paths_from_plan():
    """get_rules correctly extracts file paths from plan JSON."""
    plan = '{"steps": [{"file": "src/App.jsx"}, {"file": "api/routes.py"}]}'
    with patch.object(AgentsRulesLoader, '_load_from_disk', return_value=SMALL_AGENTS_MD):
        result = AgentsRulesLoader.get_rules(
            session_id="session-plan-paths",
            plan_str=plan,
        )
        assert len(result) > 0


def test_clear_cache():
    """clear_cache removes specific or all sessions."""
    _session_cache["session-x"] = "content x"
    _session_cache["session-y"] = "content y"

    AgentsRulesLoader.clear_cache("session-x")
    assert "session-x" not in _session_cache
    assert "session-y" in _session_cache

    AgentsRulesLoader.clear_cache()
    assert len(_session_cache) == 0


def test_split_sections():
    """_split_sections correctly divides markdown by headers."""
    sections = AgentsRulesLoader._split_sections(LARGE_AGENTS_MD)
    # Should have multiple sections
    assert len(sections) >= 5
    # First section should be the title/summary
    assert "PROJECT SUMMARY" in sections[0]["heading"] or "AI AGENT" in sections[0]["heading"]
