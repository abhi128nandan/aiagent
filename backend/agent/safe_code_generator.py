"""
Safe Code Generator — generates code fixes with safety constraints.

Generates fixes by:
  1. Gathering full context (file content, interfaces, dependents, tests)
  2. Prompting the LLM with explicit constraints (don't break contracts)
  3. Validating the generated code with StaticValidator before returning
  4. Retrying with validation feedback if the first attempt fails

Safety rules:
  - Never change function signatures that other files depend on
  - Never remove existing error handling
  - Preserve all comments and docstrings
  - Output minimal diffs, not full file rewrites
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────


@dataclass
class CodeChange:
    """A proposed code change for a specific file."""
    file: str
    original_content: str
    new_content: str
    diff_summary: str = ""
    change_type: str = "modify"   # modify, create, delete
    issue_index: int = -1
    validation_passed: bool = False
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "change_type": self.change_type,
            "diff_summary": self.diff_summary,
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
        }


# ── Safe Code Generator ──────────────────────────────────────────────


class SafeCodeGenerator:
    """
    Generates safe code fixes using LLM with full codebase context.

    Uses the knowledge graph to gather interface contracts and dependent
    files, ensuring the generated fix doesn't break existing functionality.
    """

    MAX_RETRIES = 3

    def __init__(self, workspace_root: str = "/workspace") -> None:
        self.root = workspace_root

    async def generate_fix(
        self,
        issue: Any,
        kg: Any,
        llm: Any,
        index: Any = None,
    ) -> Optional[CodeChange]:
        """
        Generate a safe fix for a single issue.

        Args:
            issue: Issue object from the analysis engine.
            kg: KnowledgeGraph for context gathering.
            llm: LLM instance for code generation.
            index: Optional WorkspaceIndex for additional context.

        Returns:
            CodeChange if successful, None if unable to fix safely.
        """
        # 1. Read the target file
        filepath = os.path.join(self.root, issue.file)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                original_content = f.read()
        except (OSError, IOError):
            logger.warning("fix_file_not_found", file=issue.file)
            return None

        # 2. Gather context from knowledge graph
        context = self._gather_context(issue, kg, original_content)

        # 3. Generate fix with retries
        for attempt in range(self.MAX_RETRIES):
            try:
                prompt = self._build_fix_prompt(issue, original_content, context, attempt)
                response = await llm.ainvoke(prompt)
                new_content = self._extract_code_from_response(
                    response, original_content
                )

                if not new_content or new_content == original_content:
                    logger.warning(
                        "fix_no_changes",
                        file=issue.file,
                        attempt=attempt + 1,
                    )
                    continue

                # 4. Validate the generated code
                validation_errors = self._validate_change(issue.file, new_content)

                if not validation_errors:
                    change = CodeChange(
                        file=issue.file,
                        original_content=original_content,
                        new_content=new_content,
                        diff_summary=self._compute_diff_summary(original_content, new_content),
                        issue_index=getattr(issue, 'issue_index', -1),
                        validation_passed=True,
                    )
                    logger.info(
                        "fix_generated",
                        file=issue.file,
                        attempt=attempt + 1,
                    )
                    return change

                # Retry with validation feedback
                context["validation_errors"] = validation_errors
                logger.info(
                    "fix_validation_failed_retrying",
                    file=issue.file,
                    attempt=attempt + 1,
                    errors=len(validation_errors),
                )

            except Exception as e:
                logger.warning(
                    "fix_generation_error",
                    file=issue.file,
                    attempt=attempt + 1,
                    error=str(e),
                )

        logger.warning("fix_generation_failed", file=issue.file)
        return None

    def _gather_context(
        self, issue: Any, kg: Any, original_content: str
    ) -> Dict[str, Any]:
        """Gather all context the LLM needs to generate a safe fix."""
        context: Dict[str, Any] = {
            "target_content": original_content,
            "issue": {
                "category": issue.category.value,
                "severity": issue.severity.value,
                "message": issue.message,
                "line": issue.line,
                "suggestion": getattr(issue, 'suggestion', ''),
                "code_snippet": getattr(issue, 'code_snippet', ''),
            },
        }

        if not kg:
            return context

        try:
            # Get dependent files (what imports this file?)
            dependents = kg.get_reverse_dependencies(issue.file)
            context["dependents"] = dependents[:5]

            # Get related files (what does this file import?)
            neighbors = kg.get_neighbors(issue.file, depth=1)
            context["neighbors"] = neighbors[:5]

            # Get interfaces this file must satisfy
            interfaces = kg.get_interfaces_used_by(issue.file)
            if interfaces:
                context["interfaces"] = [
                    {"name": iface.name, "type": iface.symbol_type, "file": iface.file}
                    for iface in interfaces[:5]
                ]

            # Get symbols defined in this file
            symbols = kg.get_symbols_in_file(issue.file)
            if symbols:
                context["symbols"] = [
                    {"name": s.name, "type": s.symbol_type, "exported": s.is_exported}
                    for s in symbols[:20]
                ]

        except Exception as e:
            logger.warning("context_gathering_error", error=str(e))

        return context

    def _build_fix_prompt(
        self,
        issue: Any,
        content: str,
        context: Dict[str, Any],
        attempt: int,
    ) -> str:
        """Build the LLM prompt for code generation."""
        parts = [
            f"Fix this issue in {issue.file}:",
            f"ISSUE ({issue.category.value}, {issue.severity.value}): {issue.message}",
            f"LINE: {issue.line}",
        ]

        if issue.suggestion:
            parts.append(f"SUGGESTED FIX: {issue.suggestion}")

        parts.append(f"\nCURRENT FILE:\n```\n{content[:8000]}\n```")

        # Add context about dependents
        if context.get("dependents"):
            parts.append(
                f"\nFILES THAT DEPEND ON THIS (do NOT break their contracts):\n"
                + "\n".join(f"  - {d}" for d in context["dependents"])
            )

        if context.get("interfaces"):
            parts.append(
                "\nINTERFACES THIS FILE MUST SATISFY:\n"
                + "\n".join(f"  - {i['name']} ({i['type']}) from {i['file']}" for i in context["interfaces"])
            )

        if context.get("symbols"):
            exported = [s for s in context["symbols"] if s["exported"]]
            if exported:
                parts.append(
                    "\nEXPORTED SYMBOLS (do NOT change signatures):\n"
                    + "\n".join(f"  - {s['name']} ({s['type']})" for s in exported[:10])
                )

        # Validation feedback from previous attempt
        if context.get("validation_errors"):
            parts.append(
                "\nPREVIOUS ATTEMPT FAILED VALIDATION:\n"
                + "\n".join(f"  ❌ {e}" for e in context["validation_errors"])
                + "\nFix these validation errors in your new attempt."
            )

        parts.extend([
            "\nRULES:",
            "- Change ONLY what's necessary to fix the issue",
            "- Do NOT change function signatures that other files depend on",
            "- Do NOT remove existing error handling",
            "- Preserve all comments and docstrings",
            "- Return the COMPLETE fixed file content wrapped in ```python or ```typescript code fence",
        ])

        return "\n".join(parts)

    def _extract_code_from_response(self, response: Any, original: str) -> Optional[str]:
        """Extract code from LLM response (inside code fences)."""
        content = response.content if hasattr(response, 'content') else str(response)

        # Try to find code in fenced blocks
        code_match = re.search(
            r'```(?:python|typescript|javascript|jsx|tsx)?\s*\n(.*?)```',
            content, re.DOTALL
        )
        if code_match:
            return code_match.group(1).strip()

        # If no code fence, try to use the full response if it looks like code
        if content.strip().startswith(("import ", "from ", "def ", "class ", "const ", "export ")):
            return content.strip()

        return None

    def _validate_change(self, path: str, content: str) -> List[str]:
        """Validate the generated code using the existing StaticValidator."""
        errors: List[str] = []
        try:
            from agent.static_validator import StaticValidator
            validator = StaticValidator()
            result = validator.validate_file(path, content)
            if not result.passed:
                errors.extend(result.errors)
        except Exception as e:
            errors.append(f"Validation error: {e}")
        return errors

    @staticmethod
    def _compute_diff_summary(original: str, new: str) -> str:
        """Compute a brief summary of changes between original and new content."""
        orig_lines = original.splitlines()
        new_lines = new.splitlines()

        added = sum(1 for line in new_lines if line not in orig_lines)
        removed = sum(1 for line in orig_lines if line not in new_lines)

        return f"+{added} lines, -{removed} lines"
