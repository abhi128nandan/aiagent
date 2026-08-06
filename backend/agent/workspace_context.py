"""
Workspace Context Builder — generates compact, LLM-friendly summaries
of the project workspace for inclusion in planning and implementation prompts.

This module bridges the WorkspaceIndexer (which does the heavy lifting
of file-system analysis) with the LLM prompt layer.  It produces:

  1. A formatted workspace summary (project type, frameworks, dependencies)
  2. Architectural constraints the LLM must respect
  3. Suggested file locations for new files
  4. Task-specific context filtering (frontend vs backend vs full)

Integrated into plan_node and implement_node per Issue #3 solution.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


# ── Feature flag ──────────────────────────────────────────────────────────

ENABLE_WORKSPACE_AWARENESS = True


def build_workspace_context(
    workspace_index: Dict[str, Any],
    max_tokens: int = 2000,
) -> str:
    """
    Build a compact workspace summary for LLM context injection.

    Args:
        workspace_index: Dict from WorkspaceIndex (serialised to dict).
                         Expected keys: project_type, framework, tech_stack,
                         dependencies, dev_dependencies, key_files,
                         entry_points, structure_tree, file_count,
                         directory_count.
        max_tokens: Approximate max tokens to consume (~4 chars/token).

    Returns:
        Formatted workspace context string.
    """
    if not ENABLE_WORKSPACE_AWARENESS or not workspace_index:
        return ""

    sections: List[str] = []

    # 1. Project overview ────────────────────────────────────────────────
    project_type = workspace_index.get("project_type", "unknown")
    framework = workspace_index.get("framework", "unknown")
    tech_stack = workspace_index.get("tech_stack", [])
    file_count = workspace_index.get("file_count", 0)
    dir_count = workspace_index.get("directory_count", 0)

    sections.append(
        f"## Project Overview\n"
        f"- **Type**: {project_type}\n"
        f"- **Framework**: {framework}\n"
        f"- **Tech Stack**: {', '.join(tech_stack) if tech_stack else 'Not detected'}\n"
        f"- **Size**: {file_count} files, {dir_count} directories"
    )

    # 2. File structure ──────────────────────────────────────────────────
    tree = workspace_index.get("structure_tree", "")
    if tree:
        tree_lines = tree.split("\n")
        if len(tree_lines) > 40:
            tree = "\n".join(tree_lines[:40]) + f"\n... ({len(tree_lines) - 40} more)"
        sections.append(f"## Directory Structure\n```\n{tree}\n```")

    # 3. Dependencies ───────────────────────────────────────────────────
    dependencies = workspace_index.get("dependencies", {})
    if dependencies:
        dep_parts: List[str] = []
        for manager, deps in dependencies.items():
            if deps:
                dep_list = ", ".join(deps[:15])
                if len(deps) > 15:
                    dep_list += f" (+ {len(deps) - 15} more)"
                dep_parts.append(f"- **{manager}**: {dep_list}")
        if dep_parts:
            sections.append(
                f"## Installed Dependencies\n" + "\n".join(dep_parts)
            )

    # 4. Key files ──────────────────────────────────────────────────────
    key_files = workspace_index.get("key_files", [])
    if key_files:
        sections.append(
            f"## Key Files\n" + "\n".join(f"- `{f}`" for f in key_files[:10])
        )

    # 5. Entry points ───────────────────────────────────────────────────
    entry_points = workspace_index.get("entry_points", [])
    if entry_points:
        sections.append(
            f"## Entry Points\n" + "\n".join(f"- `{ep}`" for ep in entry_points)
        )

    # Combine and enforce token budget
    full_context = "\n\n".join(sections)
    max_chars = max_tokens * 4
    if len(full_context) > max_chars:
        full_context = full_context[:max_chars] + "\n\n... (truncated for brevity)"

    return full_context


def get_architectural_constraints(workspace_index: Dict[str, Any]) -> str:
    """
    Extract architectural constraints that plans MUST respect.

    These constraints are injected into the planning prompt with strong
    language to override the LLM's tendency to re-scaffold from scratch.
    """
    if not workspace_index:
        return "No specific constraints detected."

    constraints: List[str] = []
    project_type = workspace_index.get("project_type", "unknown")
    framework = workspace_index.get("framework", "unknown")
    tech_stack = workspace_index.get("tech_stack", [])
    dependencies = workspace_index.get("dependencies", {})

    # Language constraints
    if project_type == "python":
        constraints.append("- MUST use Python (existing project)")
        constraints.append("- Follow PEP 8 style guidelines")
    elif project_type == "node":
        constraints.append("- MUST use Node.js/JavaScript/TypeScript (existing project)")
    elif project_type == "fullstack":
        constraints.append("- Fullstack project: Python backend + Node.js frontend")

    # Framework constraints
    framework_lower = framework.lower() if framework else ""
    if "react" in framework_lower:
        constraints.append("- MUST use React components (existing framework)")
        constraints.append("- Follow React hooks patterns")
    elif "nextjs" in framework_lower or "next" in framework_lower:
        constraints.append("- MUST use Next.js (existing framework)")
        constraints.append("- Follow App Router or Pages Router conventions")
    elif "vue" in framework_lower:
        constraints.append("- MUST use Vue.js (existing framework)")
    elif "fastapi" in framework_lower:
        constraints.append("- MUST use FastAPI routers and dependencies")
    elif "express" in framework_lower:
        constraints.append("- MUST use Express middleware patterns")
    elif "django" in framework_lower:
        constraints.append("- MUST use Django views and models")
    elif "flask" in framework_lower:
        constraints.append("- MUST use Flask blueprints and routes")

    # TypeScript detection
    if "TypeScript" in tech_stack:
        constraints.append("- MUST use TypeScript (.ts/.tsx files)")
        constraints.append("- Add proper type annotations")

    # Dependency management
    npm_deps = dependencies.get("npm", [])
    pip_deps = dependencies.get("pip", [])
    if npm_deps:
        constraints.append("- Add new npm dependencies to package.json")
        constraints.append("- DO NOT install packages already present")
    if pip_deps:
        constraints.append("- Add new Python dependencies to requirements.txt")
        constraints.append("- DO NOT install packages already present")

    # Tailwind detection
    if "Tailwind CSS" in tech_stack or "tailwindcss" in npm_deps:
        constraints.append("- Use Tailwind CSS classes for styling (existing setup)")

    return "\n".join(constraints) if constraints else "No specific constraints detected."


def suggest_file_locations(
    workspace_index: Dict[str, Any],
    file_purpose: str = "",
) -> Dict[str, str]:
    """
    Suggest appropriate file locations based on existing directory structure.

    Args:
        workspace_index: Workspace index dict.
        file_purpose: Purpose of new file (e.g. "component", "route", "model").

    Returns:
        Dict of purpose -> suggested_path.
    """
    suggestions: Dict[str, str] = {}
    tree = workspace_index.get("structure_tree", "")
    framework = (workspace_index.get("framework") or "").lower()

    # React/Next component suggestions
    if framework in ("react", "nextjs", "vite"):
        if "src/components/" in tree:
            suggestions["component"] = "src/components/"
        elif "components/" in tree:
            suggestions["component"] = "components/"
        if "src/hooks/" in tree:
            suggestions["hook"] = "src/hooks/"
        if "src/pages/" in tree or "pages/" in tree:
            suggestions["page"] = "src/pages/" if "src/pages/" in tree else "pages/"

    # Python backend suggestions
    if framework in ("fastapi", "flask", "django"):
        if "app/routes/" in tree or "app/routers/" in tree:
            suggestions["route"] = (
                "app/routes/" if "app/routes/" in tree else "app/routers/"
            )
        if "app/models/" in tree or "models/" in tree:
            suggestions["model"] = (
                "app/models/" if "app/models/" in tree else "models/"
            )
        if "app/services/" in tree or "services/" in tree:
            suggestions["service"] = (
                "app/services/" if "app/services/" in tree else "services/"
            )

    # Generic suggestions
    if "tests/" in tree or "test/" in tree:
        suggestions["test"] = "tests/" if "tests/" in tree else "test/"
    if "src/" in tree:
        suggestions["source"] = "src/"
    if "public/" in tree:
        suggestions["static"] = "public/"

    return suggestions


def build_task_specific_context(
    workspace_index: Dict[str, Any],
    task_description: str,
    max_tokens: int = 1500,
) -> str:
    """
    Build context relevant to a specific task type.

    If the task mentions "frontend" / "react", focus on frontend files.
    If the task mentions "api" / "backend", focus on backend files.
    Otherwise, provide a balanced summary.
    """
    if not workspace_index or not task_description:
        return build_workspace_context(workspace_index, max_tokens)

    task_lower = task_description.lower()

    # Detect task focus
    frontend_keywords = {"frontend", "react", "component", "ui", "css", "html",
                         "page", "layout", "style", "vue", "angular"}
    backend_keywords = {"backend", "api", "endpoint", "route", "server",
                        "database", "model", "auth", "middleware"}

    is_frontend = any(kw in task_lower for kw in frontend_keywords)
    is_backend = any(kw in task_lower for kw in backend_keywords)

    # For now, return full context (future: filter file tree by relevance)
    return build_workspace_context(workspace_index, max_tokens)
