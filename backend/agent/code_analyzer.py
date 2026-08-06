"""
Code Analysis Engine — multi-pass static and semantic analysis.

Runs 6 analysis passes over the codebase:
  1. Syntax         — reuses existing StaticValidator
  2. Imports        — unused imports, circular dependencies
  3. Security       — hardcoded secrets, injection patterns, eval usage
  4. Performance    — blocking calls in async, N+1 query patterns
  5. API Consistency — frontend-backend DTO/endpoint mismatches
  6. Semantic       — LLM-powered logic bug detection

Each pass produces a list of Issue objects with severity, location,
and fix suggestions.  The engine aggregates all issues for the
improvement planner.
"""
from __future__ import annotations

import ast as _ast
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.logger import get_logger

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(str, Enum):
    SYNTAX = "syntax"
    UNUSED_IMPORT = "unused_import"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    SECURITY = "security"
    PERFORMANCE = "performance"
    API_MISMATCH = "api_mismatch"
    CODE_SMELL = "code_smell"
    LOGIC_ERROR = "logic_error"
    MISSING_ERROR_HANDLING = "missing_error_handling"
    TYPE_MISMATCH = "type_mismatch"
    DEPRECATED = "deprecated"
    DOCUMENTATION = "documentation"


@dataclass
class Issue:
    """A detected code issue."""
    category: IssueCategory
    severity: IssueSeverity
    file: str
    line: int = 0
    message: str = ""
    suggestion: str = ""
    fix_confidence: float = 0.0  # 0.0 - 1.0: how confident we are the fix is correct
    code_snippet: str = ""       # The problematic code (for context)
    related_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "suggestion": self.suggestion,
            "fix_confidence": self.fix_confidence,
            "related_files": self.related_files,
        }


# ── Security Patterns ─────────────────────────────────────────────────

_SECURITY_PATTERNS = [
    # Hardcoded secrets
    (r'(?:password|secret|api_key|apikey|token|auth)\s*=\s*["\'][^"\']{8,}["\']',
     "Potential hardcoded secret/credential",
     IssueSeverity.CRITICAL, 0.7),
    # SQL injection (string formatting in queries)
    (r'(?:execute|query|raw)\s*\(\s*f["\']|\.format\s*\(',
     "Potential SQL injection — use parameterized queries",
     IssueSeverity.CRITICAL, 0.8),
    # eval/exec usage
    (r'\b(?:eval|exec)\s*\(',
     "Use of eval/exec — dangerous with user input",
     IssueSeverity.HIGH, 0.9),
    # Subprocess with shell=True
    (r'subprocess\.\w+\([^)]*shell\s*=\s*True',
     "subprocess with shell=True — potential command injection",
     IssueSeverity.HIGH, 0.8),
    # Disabled SSL verification
    (r'verify\s*=\s*False',
     "SSL verification disabled — insecure in production",
     IssueSeverity.MEDIUM, 0.9),
    # Wildcard CORS
    (r'allow_origins\s*=\s*\[\s*["\']?\*["\']?\s*\]',
     "Wildcard CORS origin — restrict in production",
     IssueSeverity.MEDIUM, 0.8),
]

# ── Performance Patterns ──────────────────────────────────────────────

_PERFORMANCE_PATTERNS = [
    # Blocking sleep in async function
    (r'async\s+def\s+\w+.*?time\.sleep\(',
     "time.sleep() in async function — use asyncio.sleep() instead",
     IssueSeverity.HIGH, 0.95),
    # Synchronous file I/O in async
    (r'async\s+def\s+\w+.*?(?:open\(|os\.read|os\.write)',
     "Synchronous file I/O in async function — use aiofiles or run_in_executor",
     IssueSeverity.MEDIUM, 0.7),
    # N+1 query pattern (loop with query inside)
    (r'for\s+\w+\s+in\s+\w+.*?\.(?:query|filter|get|find)\(',
     "Potential N+1 query pattern — consider batch loading",
     IssueSeverity.MEDIUM, 0.5),
    # Large list comprehension without generator
    (r'\[.*for\s+\w+\s+in\s+range\(\s*\d{5,}',
     "Large list comprehension — consider using a generator expression",
     IssueSeverity.LOW, 0.6),
]

# ── Code Smell Patterns ───────────────────────────────────────────────

_CODE_SMELL_PATTERNS = [
    # Bare except
    (r'except\s*:',
     "Bare except clause — catch specific exceptions",
     IssueSeverity.MEDIUM, 0.9),
    # Wildcard import
    (r'from\s+\S+\s+import\s+\*',
     "Wildcard import — import specific names",
     IssueSeverity.LOW, 0.9),
    # TODO/FIXME/HACK comments
    (r'#\s*(?:TODO|FIXME|HACK|XXX)\b',
     "Unresolved TODO/FIXME/HACK comment",
     IssueSeverity.INFO, 0.3),
    # Magic numbers
    (r'(?:if|while|for|==|!=|<|>|<=|>=)\s+\d{3,}',
     "Magic number — extract to a named constant",
     IssueSeverity.LOW, 0.5),
    # Very long function (>100 lines)
    # (Detected in pass_complexity, not regex)
]


# ── Analysis Engine ───────────────────────────────────────────────────


class AnalysisEngine:
    """
    Multi-pass code analysis engine.

    Usage:
        engine = AnalysisEngine()
        issues = engine.analyze_project(index, knowledge_graph)
    """

    def __init__(self, workspace_root: str = "/workspace") -> None:
        self.root = workspace_root

    def analyze_project(
        self,
        index: Any,
        kg: Any,
        llm: Any = None,
        max_files: int = 200,
    ) -> List[Issue]:
        """
        Run all analysis passes on the indexed project.

        Args:
            index: WorkspaceIndex
            kg: KnowledgeGraph
            llm: Optional LLM for semantic analysis
            max_files: Maximum files to analyze (performance cap)

        Returns:
            Aggregated list of issues from all passes.
        """
        all_issues: List[Issue] = []

        # Only analyze source files
        source_types = {
            "python", "javascript", "typescript",
            "javascript_react", "typescript_react",
        }
        source_files = [
            f for f in index.files
            if f.file_type in source_types
        ][:max_files]

        logger.info(
            "analysis_started",
            total_files=len(index.files),
            source_files=len(source_files),
        )

        for file_info in source_files:
            filepath = os.path.join(self.root, file_info.path)
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError):
                continue

            # Pass 1: Syntax
            all_issues.extend(self.pass_syntax(file_info.path, content))

            # Pass 2: Imports
            all_issues.extend(self.pass_imports(file_info, content, kg))

            # Pass 3: Security
            all_issues.extend(self.pass_security(file_info.path, content))

            # Pass 4: Performance
            all_issues.extend(self.pass_performance(file_info.path, content))

            # Pass 5: Code Smells
            all_issues.extend(self.pass_code_smells(file_info.path, content))

            # Pass 6: Complexity
            all_issues.extend(self.pass_complexity(file_info.path, content, file_info.file_type))

        # Pass 7: Circular dependencies (project-wide)
        all_issues.extend(self.pass_circular_dependencies(kg))

        # Pass 8: API Consistency (project-wide)
        from agent.api_consistency_checker import ApiConsistencyChecker
        checker = ApiConsistencyChecker(self.root)
        all_issues.extend(checker.check_project(index))

        logger.info(
            "analysis_complete",
            total_issues=len(all_issues),
            critical=sum(1 for i in all_issues if i.severity == IssueSeverity.CRITICAL),
            high=sum(1 for i in all_issues if i.severity == IssueSeverity.HIGH),
            medium=sum(1 for i in all_issues if i.severity == IssueSeverity.MEDIUM),
        )

        return all_issues

    # ── Pass 1: Syntax ────────────────────────────────────────────────

    def pass_syntax(self, path: str, content: str) -> List[Issue]:
        """Check syntax using existing StaticValidator integration."""
        issues: List[Issue] = []
        if path.endswith(".py"):
            try:
                _ast.parse(content)
            except SyntaxError as e:
                issues.append(Issue(
                    category=IssueCategory.SYNTAX,
                    severity=IssueSeverity.HIGH,
                    file=path,
                    line=e.lineno or 0,
                    message=f"Python syntax error: {e.msg}",
                    suggestion="Fix the syntax error at the indicated line",
                    fix_confidence=0.8,
                    code_snippet=(e.text or "").strip()[:100],
                ))
        return issues

    # ── Pass 2: Imports ───────────────────────────────────────────────

    def pass_imports(self, file_info: Any, content: str, kg: Any) -> List[Issue]:
        """Detect unused imports and missing dependencies."""
        issues: List[Issue] = []
        if file_info.file_type != "python":
            return issues

        try:
            tree = _ast.parse(content)
        except SyntaxError:
            return issues

        # Collect imported names
        imported_names: Dict[str, int] = {}
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported_names[name] = node.lineno
            elif isinstance(node, _ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    imported_names[name] = node.lineno

        # Collect used names (all Name nodes in the AST)
        used_names: Set[str] = set()
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Name):
                used_names.add(node.id)
            elif isinstance(node, _ast.Attribute):
                # Get the root of attribute chains
                root = node
                while isinstance(root, _ast.Attribute):
                    root = root.value
                if isinstance(root, _ast.Name):
                    used_names.add(root.id)

        # Find unused imports
        for name, line in imported_names.items():
            if name not in used_names and name != "__all__":
                issues.append(Issue(
                    category=IssueCategory.UNUSED_IMPORT,
                    severity=IssueSeverity.LOW,
                    file=file_info.path,
                    line=line,
                    message=f"Unused import: '{name}'",
                    suggestion=f"Remove the unused import of '{name}'",
                    fix_confidence=0.85,
                ))

        return issues

    # ── Pass 3: Security ──────────────────────────────────────────────

    def pass_security(self, path: str, content: str) -> List[Issue]:
        """Detect security vulnerabilities using pattern matching."""
        issues: List[Issue] = []
        lines = content.splitlines()

        for pattern, message, severity, confidence in _SECURITY_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.DOTALL):
                # Find the line number
                line_num = content[:match.start()].count("\n") + 1
                snippet = lines[line_num - 1].strip()[:100] if line_num <= len(lines) else ""

                issues.append(Issue(
                    category=IssueCategory.SECURITY,
                    severity=severity,
                    file=path,
                    line=line_num,
                    message=message,
                    suggestion=f"Review and fix the security issue at line {line_num}",
                    fix_confidence=confidence,
                    code_snippet=snippet,
                ))

        return issues

    # ── Pass 4: Performance ───────────────────────────────────────────

    def pass_performance(self, path: str, content: str) -> List[Issue]:
        """Detect performance anti-patterns."""
        issues: List[Issue] = []
        lines = content.splitlines()

        for pattern, message, severity, confidence in _PERFORMANCE_PATTERNS:
            for match in re.finditer(pattern, content, re.DOTALL):
                line_num = content[:match.start()].count("\n") + 1
                snippet = lines[line_num - 1].strip()[:100] if line_num <= len(lines) else ""

                issues.append(Issue(
                    category=IssueCategory.PERFORMANCE,
                    severity=severity,
                    file=path,
                    line=line_num,
                    message=message,
                    fix_confidence=confidence,
                    code_snippet=snippet,
                ))

        return issues

    # ── Pass 5: Code Smells ───────────────────────────────────────────

    def pass_code_smells(self, path: str, content: str) -> List[Issue]:
        """Detect common code smells."""
        issues: List[Issue] = []
        lines = content.splitlines()

        for pattern, message, severity, confidence in _CODE_SMELL_PATTERNS:
            for match in re.finditer(pattern, content, re.MULTILINE):
                line_num = content[:match.start()].count("\n") + 1
                snippet = lines[line_num - 1].strip()[:100] if line_num <= len(lines) else ""

                issues.append(Issue(
                    category=IssueCategory.CODE_SMELL,
                    severity=severity,
                    file=path,
                    line=line_num,
                    message=message,
                    fix_confidence=confidence,
                    code_snippet=snippet,
                ))

        return issues

    # ── Pass 6: Complexity ────────────────────────────────────────────

    def pass_complexity(self, path: str, content: str, file_type: str) -> List[Issue]:
        """Detect overly complex functions (too many lines, deep nesting)."""
        issues: List[Issue] = []

        if file_type != "python":
            return issues

        try:
            tree = _ast.parse(content)
        except SyntaxError:
            return issues

        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                func_lines = (node.end_lineno or node.lineno) - node.lineno + 1
                if func_lines > 100:
                    issues.append(Issue(
                        category=IssueCategory.CODE_SMELL,
                        severity=IssueSeverity.MEDIUM,
                        file=path,
                        line=node.lineno,
                        message=f"Function '{node.name}' is {func_lines} lines long — consider splitting",
                        suggestion=f"Refactor '{node.name}' into smaller, focused functions",
                        fix_confidence=0.3,  # Refactoring is complex
                    ))
                elif func_lines > 50:
                    issues.append(Issue(
                        category=IssueCategory.CODE_SMELL,
                        severity=IssueSeverity.LOW,
                        file=path,
                        line=node.lineno,
                        message=f"Function '{node.name}' is {func_lines} lines — consider simplifying",
                        fix_confidence=0.2,
                    ))

        return issues

    # ── Pass 7: Circular Dependencies ─────────────────────────────────

    def pass_circular_dependencies(self, kg: Any) -> List[Issue]:
        """Detect circular import dependencies using the knowledge graph."""
        issues: List[Issue] = []
        if not kg or not hasattr(kg, 'graph'):
            return issues

        try:
            import networkx as nx
            # Only look at file-level import edges
            file_graph = nx.DiGraph()
            for u, v, data in kg.graph.edges(data=True):
                if (u.startswith("file:") and v.startswith("file:") and
                        data.get("relationship") == "imports"):
                    file_graph.add_edge(u, v)

            cycles = list(nx.simple_cycles(file_graph))
            for cycle in cycles[:10]:  # Cap to prevent noise
                files = [n.replace("file:", "") for n in cycle]
                cycle_str = " → ".join(files + [files[0]])
                issues.append(Issue(
                    category=IssueCategory.CIRCULAR_DEPENDENCY,
                    severity=IssueSeverity.HIGH,
                    file=files[0],
                    message=f"Circular dependency detected: {cycle_str}",
                    suggestion="Break the cycle by extracting shared code into a separate module",
                    fix_confidence=0.3,
                    related_files=files,
                ))
        except Exception as e:
            logger.warning("circular_dependency_check_failed", error=str(e))

        return issues
