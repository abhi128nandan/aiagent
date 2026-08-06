"""
Static Validation — lightweight pre-execution syntax checks.

Catches obvious errors (mismatched braces, Python syntax errors, invalid JSON)
*before* wasting Docker execution time.  Integrated into the implementation
node as an internal retry loop (Issue #2 in WORKFLOW_ISSUES.md).

Design decisions:
  - Python uses the stdlib `ast` module (zero dependencies, fast).
  - JS/TS uses simple bracket-counting heuristics — NOT a full parser.
    This intentionally trades recall for speed: we catch ~60-70% of
    syntax errors at near-zero cost.  The remaining 30% are caught by
    the Docker execution phase.
  - JSON uses `json.loads`.
  - Validators return structured `ValidationResult` objects so the
    implement node can include actionable fix suggestions in the LLM
    prompt.
"""

import ast
import re
import json
from typing import Dict, List
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


# ── Configuration ──────────────────────────────────────────────────────────

ENABLE_STATIC_VALIDATION = True
MAX_INTERNAL_VALIDATION_RETRIES = 3
WARNINGS_AS_ERRORS = False


@dataclass
class ValidationResult:
    """Result of static validation."""
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    category: str = "none"   # "syntax", "imports", "structure", "none"


class StaticValidator:
    """
    Lightweight static validation for generated code.
    Catches obvious errors before Docker execution.
    """

    def validate_file(self, path: str, content: str) -> ValidationResult:
        """Validate file based on extension."""
        if not ENABLE_STATIC_VALIDATION:
            return ValidationResult(passed=True)

        if path.endswith('.py'):
            return self.validate_python(content)
        elif path.endswith(('.ts', '.tsx', '.js', '.jsx')):
            return self.validate_javascript(content)
        elif path.endswith('.json'):
            return self.validate_json(content)
        elif path.endswith(('.html', '.htm')):
            return self.validate_html(content)
        else:
            return ValidationResult(passed=True)

    # ── Python ─────────────────────────────────────────────────────────

    def validate_python(self, content: str) -> ValidationResult:
        """Validate Python syntax using the stdlib AST parser."""
        errors: List[str] = []
        warnings: List[str] = []

        try:
            ast.parse(content)
        except SyntaxError as e:
            line_info = f" at line {e.lineno}" if e.lineno else ""
            text_info = f"\n  {e.text.rstrip()}" if e.text else ""
            errors.append(
                f"Python syntax error{line_info}: {e.msg}{text_info}"
            )
            return ValidationResult(
                passed=False,
                errors=errors,
                warnings=warnings,
                category="syntax",
            )
        except Exception as e:
            errors.append(f"Python parse error: {e}")
            return ValidationResult(
                passed=False,
                errors=errors,
                warnings=warnings,
                category="syntax",
            )

        # Lightweight warnings (non-blocking)
        warnings.extend(self._check_python_warnings(content))

        return ValidationResult(
            passed=True,
            errors=errors,
            warnings=warnings,
            category="none",
        )

    # ── JavaScript / TypeScript ────────────────────────────────────────

    def validate_javascript(self, content: str) -> ValidationResult:
        """
        Validate JS/TS with simple heuristic checks.

        NOTE: This is intentionally basic — a full parse requires a JS
        engine.  We focus on high-signal, low-false-positive checks.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Strip string literals and template literals to avoid false positives
        # on bracket counts (e.g. `console.log("{")`).
        stripped = self._strip_js_strings(content)

        # 1. Unmatched curly braces
        if stripped.count('{') != stripped.count('}'):
            diff = stripped.count('{') - stripped.count('}')
            direction = "opening" if diff > 0 else "closing"
            errors.append(
                f"Unmatched curly braces: {abs(diff)} extra {direction} brace(s)"
            )

        # 2. Unmatched parentheses
        if stripped.count('(') != stripped.count(')'):
            diff = stripped.count('(') - stripped.count(')')
            direction = "opening" if diff > 0 else "closing"
            errors.append(
                f"Unmatched parentheses: {abs(diff)} extra {direction} paren(s)"
            )

        # 3. Unmatched brackets
        if stripped.count('[') != stripped.count(']'):
            diff = stripped.count('[') - stripped.count(']')
            direction = "opening" if diff > 0 else "closing"
            errors.append(
                f"Unmatched square brackets: {abs(diff)} extra {direction} bracket(s)"
            )

        if errors:
            return ValidationResult(
                passed=False,
                errors=errors,
                warnings=warnings,
                category="syntax",
            )

        return ValidationResult(
            passed=True,
            errors=errors,
            warnings=warnings,
            category="none",
        )

    # ── JSON ───────────────────────────────────────────────────────────

    def validate_json(self, content: str) -> ValidationResult:
        """Validate JSON syntax."""
        try:
            json.loads(content)
            return ValidationResult(passed=True)
        except json.JSONDecodeError as e:
            return ValidationResult(
                passed=False,
                errors=[f"JSON error at line {e.lineno}, col {e.colno}: {e.msg}"],
                category="syntax",
            )

    # ── HTML ───────────────────────────────────────────────────────────

    def validate_html(self, content: str) -> ValidationResult:
        """Very basic HTML sanity check."""
        warnings: List[str] = []

        # Check for unclosed tags (very rough heuristic)
        open_tags = re.findall(r'<(\w+)[\s>]', content)
        close_tags = re.findall(r'</(\w+)>', content)
        self_closing = {'br', 'hr', 'img', 'input', 'meta', 'link',
                        'area', 'base', 'col', 'embed', 'source',
                        'track', 'wbr', '!doctype', '!DOCTYPE'}

        open_counts: Dict[str, int] = {}
        for tag in open_tags:
            tag_lower = tag.lower()
            if tag_lower not in self_closing:
                open_counts[tag_lower] = open_counts.get(tag_lower, 0) + 1

        close_counts: Dict[str, int] = {}
        for tag in close_tags:
            close_counts[tag.lower()] = close_counts.get(tag.lower(), 0) + 1

        for tag, count in open_counts.items():
            closed = close_counts.get(tag, 0)
            if count > closed:
                warnings.append(f"Possibly unclosed <{tag}> tag(s): {count - closed} unmatched")

        return ValidationResult(
            passed=True,  # HTML warnings don't block execution
            warnings=warnings,
            category="none",
        )

    # ── Batch validation ───────────────────────────────────────────────

    def validate_actions(self, actions: List[Dict]) -> ValidationResult:
        """
        Validate all write_file actions in a batch.

        Args:
            actions: List of action dicts with 'action', 'path', 'content' keys.

        Returns:
            Aggregated ValidationResult.
        """
        all_errors: List[str] = []
        all_warnings: List[str] = []

        for action in actions:
            action_type = action.get("action") or action.get("type", "")
            if action_type in ("write_file", "write"):
                path = action.get("path", "")
                content = action.get("content", "")
                result = self.validate_file(path, content)
                if result.errors:
                    all_errors.extend(
                        f"[{path}] {err}" for err in result.errors
                    )
                if result.warnings:
                    all_warnings.extend(
                        f"[{path}] {warn}" for warn in result.warnings
                    )

        return ValidationResult(
            passed=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            category="syntax" if all_errors else "none",
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _check_python_warnings(self, content: str) -> List[str]:
        """Non-blocking Python quality checks."""
        warnings: List[str] = []

        # Check for common anti-patterns
        if 'import *' in content:
            warnings.append("Wildcard import detected (import *)")

        # Check for bare except clauses
        if re.search(r'except\s*:', content, re.MULTILINE):
            warnings.append("Bare except clause — consider catching specific exceptions")

        return warnings

    @staticmethod
    def _strip_js_strings(content: str) -> str:
        """
        Remove string literals and template literals from JS/TS content
        to avoid false positives in bracket-counting heuristics.
        """
        # Remove template literals (backtick strings)
        stripped = re.sub(r'`[^`]*`', '""', content, flags=re.DOTALL)
        # Remove double-quoted strings
        stripped = re.sub(r'"(?:[^"\\]|\\.)*"', '""', stripped)
        # Remove single-quoted strings
        stripped = re.sub(r"'(?:[^'\\]|\\.)*'", "''", stripped)
        # Remove single-line comments
        stripped = re.sub(r'//.*$', '', stripped, flags=re.MULTILINE)
        # Remove multi-line comments
        stripped = re.sub(r'/\*.*?\*/', '', stripped, flags=re.DOTALL)
        return stripped

    def validate_content_alignment(self, path: str, content: str, plan_str: str = '') -> ValidationResult:
        """
        Pre-write content alignment check.

        Detects code that should NOT be written to the sandbox:
        1. Unmodified Vite/React counter boilerplate
        2. Spring Boot empty skeleton classes
        3. Placeholder / TODO / FIXME comments in critical files
        4. Empty or near-empty file bodies

        This runs BEFORE the file is written to the Docker sandbox,
        catching bad content at the source rather than waiting for
        the final validation node.
        """
        errors: List[str] = []
        warnings: List[str] = []

        stripped = content.strip()

        # ── Check 1: Empty / trivially small files ─────────────────────
        if not stripped:
            errors.append(f"File {path} is empty — nothing to write.")
            return ValidationResult(passed=False, errors=errors, category="structure")

        # ── Check 2: Vite/React boilerplate detection ──────────────────
        if path in ('src/App.jsx', 'src/App.tsx', 'App.jsx', 'App.tsx'):
            has_counter = "setCount" in content and "useState(0)" in content
            has_vite_heading = "Vite + React" in content or "Vite and React logos" in content
            has_logo_imports = "reactLogo" in content and "viteLogo" in content
            if has_counter and (has_vite_heading or has_logo_imports):
                errors.append(
                    f"File {path} contains unmodified Vite + React counter boilerplate. "
                    f"You MUST replace this with the actual application UI as described in the plan."
                )
                return ValidationResult(passed=False, errors=errors, category="structure")

        # ── Check 3: Spring Boot empty skeleton detection ──────────────
        if path.endswith('.java'):
            # An empty controller/service with only class declaration and no methods
            has_class = re.search(r'public\s+class\s+\w+', content)
            method_count = len(re.findall(r'(?:public|private|protected)\s+\w+\s+\w+\s*\(', content))
            if has_class and method_count <= 1 and len(stripped.splitlines()) < 15:
                warnings.append(
                    f"File {path} appears to be a skeleton Java class with no real methods. "
                    f"Ensure it implements the required business logic."
                )

        # ── Check 4: Placeholder / TODO / FIXME in comments ────────────
        # Only flag these in application source files, not configs
        is_source_file = any(path.endswith(ext) for ext in (
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.kt', '.go', '.rs',
        ))
        if is_source_file:
            placeholder_patterns = [
                (r'(?i)#\s*TODO\b', 'TODO'),
                (r'(?i)//\s*TODO\b', 'TODO'),
                (r'(?i)/\*\s*TODO\b', 'TODO'),
                (r'(?i)#\s*FIXME\b', 'FIXME'),
                (r'(?i)//\s*FIXME\b', 'FIXME'),
                (r'(?i)#\s*PLACEHOLDER\b', 'PLACEHOLDER'),
                (r'(?i)//\s*PLACEHOLDER\b', 'PLACEHOLDER'),
                (r'(?i)//\s*INSERT\s+CODE\s+HERE', 'INSERT CODE HERE'),
                (r'(?i)#\s*INSERT\s+CODE\s+HERE', 'INSERT CODE HERE'),
                (r'(?i)//\s*IMPLEMENT\s+HERE', 'IMPLEMENT HERE'),
                (r'(?i)#\s*IMPLEMENT\s+HERE', 'IMPLEMENT HERE'),
            ]
            found_placeholders = []
            lines = content.splitlines()
            for line_num, line in enumerate(lines, 1):
                for pattern, label in placeholder_patterns:
                    if re.search(pattern, line):
                        found_placeholders.append(f"line {line_num}: {label} — {line.strip()[:80]}")
                        break  # one match per line is enough

            if found_placeholders:
                errors.append(
                    f"File {path} contains placeholder comments that indicate incomplete code:\n"
                    + "\n".join(f"  • {p}" for p in found_placeholders[:3])
                    + "\nYou must implement the actual logic, not leave TODO/FIXME stubs."
                )
                return ValidationResult(passed=False, errors=errors, category="structure")

        return ValidationResult(passed=True, warnings=warnings, category="none")

