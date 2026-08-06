"""
Workspace Awareness — project structure indexing and architecture detection.

Architecture (from AUTONOMOUS_AI_AGENT_ARCHITECTURE.md §6):
  - File system indexing with classification
  - Dependency graph analysis (package.json, requirements.txt)
  - Import/export extraction (Python, JS/TS)
  - Architecture / framework detection
  - Compact workspace summary for LLM context
"""
from __future__ import annotations

import ast as _ast
import hashlib
import os
import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path

from core.logger import get_logger

logger = get_logger(__name__)


def compute_file_hash(content: str) -> str:
    """Compute SHA256 hash of file content for incremental change detection."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


# ── File classification ────────────────────────────────────────────────

FILE_TYPE_MAP = {
    # Source
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript_react",
    ".ts": "typescript",
    ".tsx": "typescript_react",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    # Web
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    # Data
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".csv": "csv",
    # Config
    ".env": "env",
    ".gitignore": "gitignore",
    ".dockerignore": "dockerignore",
    # Docs
    ".md": "markdown",
    ".txt": "text",
    ".rst": "rst",
    # Build
    ".lock": "lockfile",
    ".sh": "shell",
    ".bat": "batch",
    "Dockerfile": "dockerfile",
    "Makefile": "makefile",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", ".cache", ".tox",
    "coverage", ".nyc_output", "eggs", "*.egg-info",
}

KEY_FILES = {
    "package.json", "tsconfig.json", "vite.config.ts", "vite.config.js",
    "next.config.js", "next.config.mjs", "webpack.config.js",
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "Pipfile", "poetry.lock", "Cargo.toml", "go.mod",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile", ".env", ".env.example",
    "README.md", "README.rst",
    "main.py", "app.py", "manage.py", "index.ts", "index.js",
    "App.tsx", "App.jsx", "App.vue",
}


@dataclass
class SymbolInfo:
    """A code symbol (class, function, variable) extracted from a file."""
    name: str
    symbol_type: str  # 'class', 'function', 'variable', 'constant'
    line_start: int = 0
    line_end: int = 0
    docstring: str = ""
    decorators: List[str] = field(default_factory=list)
    bases: List[str] = field(default_factory=list)  # For classes: parent classes
    parameters: List[str] = field(default_factory=list)  # For functions: param names
    is_async: bool = False
    is_exported: bool = False


@dataclass
class FileInfo:
    """Metadata about a single file in the workspace."""
    path: str
    file_type: str
    size: int = 0
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    symbols: List[SymbolInfo] = field(default_factory=list)
    content_hash: str = ""  # SHA256 for incremental change detection
    is_key_file: bool = False


@dataclass
class WorkspaceIndex:
    """Complete workspace analysis result."""
    project_type: str = "unknown"        # node, python, fullstack, etc.
    framework: str = "unknown"           # react, nextjs, fastapi, express, etc.
    files: List[FileInfo] = field(default_factory=list)
    file_count: int = 0
    directory_count: int = 0
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    dev_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    key_files: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    structure_tree: str = ""


# ── Framework detection patterns ───────────────────────────────────────

FRAMEWORK_PATTERNS = {
    "react": {
        "files": ["src/App.tsx", "src/App.jsx", "src/App.js"],
        "deps": ["react", "react-dom"],
    },
    "nextjs": {
        "files": ["next.config.js", "next.config.mjs", "pages/", "app/"],
        "deps": ["next"],
    },
    "vue": {
        "files": ["src/App.vue", "vue.config.js"],
        "deps": ["vue"],
    },
    "angular": {
        "files": ["angular.json", "src/app/app.component.ts"],
        "deps": ["@angular/core"],
    },
    "express": {
        "deps": ["express"],
    },
    "fastapi": {
        "deps": ["fastapi"],
        "imports": ["from fastapi", "import fastapi"],
    },
    "django": {
        "files": ["manage.py", "settings.py"],
        "deps": ["django", "Django"],
    },
    "flask": {
        "deps": ["flask", "Flask"],
        "imports": ["from flask", "import flask"],
    },
    "vite": {
        "files": ["vite.config.ts", "vite.config.js"],
        "deps": ["vite"],
    },
    "svelte": {
        "files": ["svelte.config.js"],
        "deps": ["svelte"],
    },
}


class WorkspaceIndexer:
    """
    Indexes a workspace directory to understand project structure.

    Used by the agent to:
      1. Know what files exist before implementing
      2. Understand the tech stack and architecture
      3. Detect dependencies and entry points
      4. Provide compact context to the LLM
    """

    def __init__(self, workspace_root: str = "/workspace"):
        self.root = workspace_root

    def index(self, max_depth: int = 6) -> WorkspaceIndex:
        """
        Perform a full workspace analysis.

        Args:
            max_depth: Maximum directory depth to traverse

        Returns:
            WorkspaceIndex with complete project analysis
        """
        idx = WorkspaceIndex()

        # 1. Walk the file system
        self._walk_files(idx, max_depth)

        # 2. Parse dependency files
        self._parse_dependencies(idx)

        # 3. Detect framework and project type
        self._detect_framework(idx)

        # 4. Find entry points
        self._find_entry_points(idx)

        # 5. Build tech stack summary
        self._build_tech_stack(idx)

        # 6. Generate tree structure
        idx.structure_tree = self._generate_tree(idx)

        logger.info(
            "workspace_indexed",
            files=idx.file_count,
            dirs=idx.directory_count,
            project_type=idx.project_type,
            framework=idx.framework,
        )

        return idx

    def _walk_files(self, idx: WorkspaceIndex, max_depth: int) -> None:
        """Walk the workspace tree and collect file info."""
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Skip hidden/build directories
            dirnames[:] = [
                d for d in dirnames
                if d not in SKIP_DIRS and not d.startswith(".")
            ]

            # Enforce max depth
            rel = os.path.relpath(dirpath, self.root)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > max_depth:
                dirnames.clear()
                continue

            idx.directory_count += 1

            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                relpath = os.path.relpath(filepath, self.root)

                # Skip binary and large files
                try:
                    size = os.path.getsize(filepath)
                except OSError:
                    continue

                if size > 1_000_000:  # Skip files > 1MB
                    continue

                # Classify file
                ext = os.path.splitext(filename)[1]
                file_type = FILE_TYPE_MAP.get(ext, FILE_TYPE_MAP.get(filename, "other"))
                is_key = filename in KEY_FILES

                info = FileInfo(
                    path=relpath,
                    file_type=file_type,
                    size=size,
                    is_key_file=is_key,
                )

                # Extract imports for source files (limited to small files)
                if file_type in ("python", "javascript", "typescript",
                                 "javascript_react", "typescript_react") and size < 100_000:
                    try:
                        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        info.imports = self._extract_imports(content, file_type)
                        info.exports = self._extract_exports(content, file_type)
                        info.symbols = self._extract_symbols(content, file_type)
                        info.content_hash = compute_file_hash(content)
                    except Exception:
                        pass

                idx.files.append(info)
                idx.file_count += 1

                if is_key:
                    idx.key_files.append(relpath)

    def _extract_imports(self, content: str, file_type: str) -> List[str]:
        """Extract import statements from source files."""
        imports = []

        if file_type == "python":
            # import X / from X import Y
            for match in re.finditer(
                r'^(?:from\s+(\S+)\s+import|import\s+(\S+))', content, re.MULTILINE
            ):
                module = match.group(1) or match.group(2)
                if module:
                    imports.append(module.split(".")[0])

        elif file_type in ("javascript", "typescript", "javascript_react", "typescript_react"):
            # import X from 'Y' / require('Y')
            for match in re.finditer(r"(?:import\s+.*?from\s+|require\s*\(\s*)['\"]([^'\"]+)['\"]", content):
                imports.append(match.group(1))

        return list(set(imports))

    def _extract_exports(self, content: str, file_type: str) -> List[str]:
        """Extract export statements from source files."""
        exports = []

        if file_type == "python":
            # def X / class X
            for match in re.finditer(r'^(?:def|class)\s+(\w+)', content, re.MULTILINE):
                exports.append(match.group(1))

        elif file_type in ("javascript", "typescript", "javascript_react", "typescript_react"):
            # export (default)? function/class/const X
            for match in re.finditer(
                r'export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)', content
            ):
                exports.append(match.group(1))

        return exports[:20]  # Limit to prevent bloat

    def _extract_symbols(self, content: str, file_type: str) -> List[SymbolInfo]:
        """Extract code symbols (classes, functions, variables) from source files."""
        if file_type == "python":
            return self._extract_python_symbols(content)
        elif file_type in ("javascript", "typescript", "javascript_react", "typescript_react"):
            return self._extract_js_symbols(content)
        return []

    def _extract_python_symbols(self, content: str) -> List[SymbolInfo]:
        """Extract symbols from Python files using the stdlib AST parser."""
        symbols: List[SymbolInfo] = []
        try:
            tree = _ast.parse(content)
        except SyntaxError:
            return symbols

        for node in _ast.iter_child_nodes(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                docstring = _ast.get_docstring(node) or ""
                decorators = []
                for dec in node.decorator_list:
                    if isinstance(dec, _ast.Name):
                        decorators.append(dec.id)
                    elif isinstance(dec, _ast.Attribute):
                        decorators.append(f"{getattr(dec.value, 'id', '?')}.{dec.attr}")
                params = [
                    arg.arg for arg in node.args.args
                    if arg.arg != "self" and arg.arg != "cls"
                ]
                symbols.append(SymbolInfo(
                    name=node.name,
                    symbol_type="function",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=docstring[:200],
                    decorators=decorators,
                    parameters=params[:10],
                    is_async=isinstance(node, _ast.AsyncFunctionDef),
                    is_exported=not node.name.startswith("_"),
                ))
            elif isinstance(node, _ast.ClassDef):
                docstring = _ast.get_docstring(node) or ""
                bases = []
                for base in node.bases:
                    if isinstance(base, _ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, _ast.Attribute):
                        bases.append(f"{getattr(base.value, 'id', '?')}.{base.attr}")
                decorators = []
                for dec in node.decorator_list:
                    if isinstance(dec, _ast.Name):
                        decorators.append(dec.id)
                symbols.append(SymbolInfo(
                    name=node.name,
                    symbol_type="class",
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    docstring=docstring[:200],
                    decorators=decorators,
                    bases=bases,
                    is_exported=not node.name.startswith("_"),
                ))
            elif isinstance(node, _ast.Assign):
                for target in node.targets:
                    if isinstance(target, _ast.Name) and target.id.isupper():
                        symbols.append(SymbolInfo(
                            name=target.id,
                            symbol_type="constant",
                            line_start=node.lineno,
                            line_end=node.end_lineno or node.lineno,
                            is_exported=not target.id.startswith("_"),
                        ))

        return symbols[:100]  # Cap to prevent memory bloat

    def _extract_js_symbols(self, content: str) -> List[SymbolInfo]:
        """Extract symbols from JS/TS files using regex (lightweight, no JS engine needed)."""
        symbols: List[SymbolInfo] = []

        # Functions: export? (async)? function name(
        for match in re.finditer(
            r'^(?:export\s+(?:default\s+)?)?'
            r'(async\s+)?function\s+(\w+)\s*\(',
            content, re.MULTILINE
        ):
            symbols.append(SymbolInfo(
                name=match.group(2),
                symbol_type="function",
                line_start=content[:match.start()].count('\n') + 1,
                is_async=bool(match.group(1)),
                is_exported='export' in content[max(0, match.start() - 20):match.start() + 10],
            ))

        # Arrow functions: export? const name = (async)? (...) =>
        for match in re.finditer(
            r'(?:export\s+(?:default\s+)?)?(?:const|let|var)\s+(\w+)\s*=\s*(async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>',
            content, re.MULTILINE
        ):
            symbols.append(SymbolInfo(
                name=match.group(1),
                symbol_type="function",
                line_start=content[:match.start()].count('\n') + 1,
                is_async=bool(match.group(2)),
                is_exported='export' in content[max(0, match.start() - 20):match.start() + 10],
            ))

        # Classes: export? class Name (extends Base)?
        for match in re.finditer(
            r'(?:export\s+(?:default\s+)?)?class\s+(\w+)(?:\s+extends\s+(\w+))?',
            content, re.MULTILINE
        ):
            bases = [match.group(2)] if match.group(2) else []
            symbols.append(SymbolInfo(
                name=match.group(1),
                symbol_type="class",
                line_start=content[:match.start()].count('\n') + 1,
                bases=bases,
                is_exported='export' in content[max(0, match.start() - 20):match.start() + 10],
            ))

        # Interfaces / Types (TypeScript): export? interface/type Name
        for match in re.finditer(
            r'(?:export\s+)?(?:interface|type)\s+(\w+)',
            content, re.MULTILINE
        ):
            symbols.append(SymbolInfo(
                name=match.group(1),
                symbol_type="interface",
                line_start=content[:match.start()].count('\n') + 1,
                is_exported='export' in content[max(0, match.start() - 20):match.start() + 10],
            ))

        return symbols[:100]

    def _parse_dependencies(self, idx: WorkspaceIndex) -> None:
        """Parse dependency files (package.json, requirements.txt, etc.)."""
        # package.json
        pkg_path = os.path.join(self.root, "package.json")
        if os.path.exists(pkg_path):
            try:
                with open(pkg_path, "r") as f:
                    pkg = json.load(f)
                idx.dependencies["npm"] = list(pkg.get("dependencies", {}).keys())
                idx.dev_dependencies["npm"] = list(pkg.get("devDependencies", {}).keys())
            except Exception:
                pass

        # requirements.txt
        req_path = os.path.join(self.root, "requirements.txt")
        if os.path.exists(req_path):
            try:
                with open(req_path, "r") as f:
                    deps = []
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith("-"):
                            # Extract package name (before ==, >=, etc.)
                            pkg_name = re.split(r"[=<>!~]", line)[0].strip()
                            if pkg_name:
                                deps.append(pkg_name)
                    idx.dependencies["pip"] = deps
            except Exception:
                pass

        # pyproject.toml (basic parsing)
        pyproject_path = os.path.join(self.root, "pyproject.toml")
        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, "r") as f:
                    content = f.read()
                # Very basic TOML parsing for dependencies
                dep_section = re.search(
                    r'\[project\.dependencies\]\s*\n((?:.*\n)*?)(?:\[|$)', content
                )
                if dep_section:
                    for match in re.finditer(r'"([^"]+)"', dep_section.group(1)):
                        pkg = re.split(r"[=<>!~]", match.group(1))[0].strip()
                        idx.dependencies.setdefault("pip", []).append(pkg)
            except Exception:
                pass

    def _detect_framework(self, idx: WorkspaceIndex) -> None:
        """Detect the framework and project type from files and dependencies."""
        all_deps = set()
        for deps in idx.dependencies.values():
            all_deps.update(deps)
        for deps in idx.dev_dependencies.values():
            all_deps.update(deps)

        all_files = {fi.path for fi in idx.files}

        detected_frameworks = []

        for fw_name, patterns in FRAMEWORK_PATTERNS.items():
            score = 0

            # Check dependency matches
            fw_deps = set(patterns.get("deps", []))
            if fw_deps & all_deps:
                score += 3

            # Check file matches
            for fp in patterns.get("files", []):
                if fp.endswith("/"):
                    # Directory check
                    if any(f.startswith(fp) for f in all_files):
                        score += 2
                elif fp in all_files:
                    score += 2

            if score > 0:
                detected_frameworks.append((score, fw_name))

        detected_frameworks.sort(key=lambda x: x[0], reverse=True)

        if detected_frameworks:
            idx.framework = detected_frameworks[0][1]

        # Determine project type
        has_python = "pip" in idx.dependencies or any(
            fi.file_type == "python" for fi in idx.files
        )
        has_node = "npm" in idx.dependencies or any(
            fi.file_type in ("javascript", "typescript", "javascript_react", "typescript_react")
            for fi in idx.files
        )

        if has_python and has_node:
            idx.project_type = "fullstack"
        elif has_python:
            idx.project_type = "python"
        elif has_node:
            idx.project_type = "node"
        else:
            idx.project_type = "unknown"

    def _find_entry_points(self, idx: WorkspaceIndex) -> None:
        """Identify likely entry points."""
        entry_patterns = [
            "main.py", "app.py", "manage.py", "server.py",
            "index.ts", "index.js", "main.ts", "main.js",
            "src/index.ts", "src/index.js", "src/main.ts", "src/main.tsx",
            "src/App.tsx", "src/App.jsx",
        ]

        for pattern in entry_patterns:
            if any(fi.path == pattern for fi in idx.files):
                idx.entry_points.append(pattern)

    def _build_tech_stack(self, idx: WorkspaceIndex) -> None:
        """Build a human-readable tech stack list."""
        stack = set()

        # From framework detection
        if idx.framework != "unknown":
            stack.add(idx.framework.capitalize())

        # From dependencies
        tech_mapping = {
            "react": "React", "react-dom": "React",
            "vue": "Vue.js", "svelte": "Svelte",
            "next": "Next.js", "nuxt": "Nuxt",
            "express": "Express.js", "koa": "Koa",
            "fastapi": "FastAPI", "flask": "Flask", "django": "Django",
            "prisma": "Prisma", "mongoose": "Mongoose", "sqlalchemy": "SQLAlchemy",
            "tailwindcss": "Tailwind CSS", "styled-components": "Styled Components",
            "zustand": "Zustand", "redux": "Redux",
            "vite": "Vite", "webpack": "Webpack",
            "typescript": "TypeScript",
            "jest": "Jest", "vitest": "Vitest", "pytest": "pytest",
        }

        for deps in list(idx.dependencies.values()) + list(idx.dev_dependencies.values()):
            for dep in deps:
                dep_lower = dep.lower()
                if dep_lower in tech_mapping:
                    stack.add(tech_mapping[dep_lower])

        # From file types
        file_types = {fi.file_type for fi in idx.files}
        if "typescript" in file_types or "typescript_react" in file_types:
            stack.add("TypeScript")
        if "python" in file_types:
            stack.add("Python")

        idx.tech_stack = sorted(stack)

    def _generate_tree(self, idx: WorkspaceIndex, max_lines: int = 50) -> str:
        """Generate a compact directory tree string."""
        lines = []
        dirs_seen: Set[str] = set()

        # Sort files by path
        sorted_files = sorted(idx.files, key=lambda f: f.path)

        for fi in sorted_files:
            parts = fi.path.split("/")

            # Add directory entries
            for i in range(len(parts) - 1):
                dir_path = "/".join(parts[: i + 1])
                if dir_path not in dirs_seen:
                    dirs_seen.add(dir_path)
                    indent = "  " * i
                    lines.append(f"{indent}{parts[i]}/")

            # Add file entry
            indent = "  " * (len(parts) - 1)
            marker = " *" if fi.is_key_file else ""
            lines.append(f"{indent}{parts[-1]}{marker}")

            if len(lines) >= max_lines:
                lines.append(f"... and {len(sorted_files) - max_lines} more files")
                break

        return "\n".join(lines)

    def summarize(self, idx: WorkspaceIndex) -> str:
        """
        Generate a compact workspace summary suitable for LLM context injection.

        Designed to fit within the workspace token budget (~2000 tokens).
        """
        parts = [
            f"PROJECT STRUCTURE SUMMARY:",
            f"  Type: {idx.project_type}",
            f"  Framework: {idx.framework}",
            f"  Files: {idx.file_count} | Directories: {idx.directory_count}",
        ]

        if idx.tech_stack:
            parts.append(f"  Tech Stack: {', '.join(idx.tech_stack)}")

        if idx.entry_points:
            parts.append(f"  Entry Points: {', '.join(idx.entry_points)}")

        if idx.key_files:
            parts.append(f"  Key Files: {', '.join(idx.key_files[:10])}")

        if idx.dependencies:
            for manager, deps in idx.dependencies.items():
                if deps:
                    parts.append(f"  {manager} deps: {', '.join(deps[:15])}")

        if idx.structure_tree:
            # Limit tree to fit context
            tree_lines = idx.structure_tree.split("\n")[:30]
            parts.append(f"\n  Directory Tree:\n" + "\n".join(f"    {l}" for l in tree_lines))

        return "\n".join(parts)

    def get_ranked_context(
        self,
        idx: WorkspaceIndex,
        plan_files: List[str] = None,
        error_file: str = None,
        query: str = None,
        max_tokens: int = 4000
    ) -> str:
        """
        Collects, ranks, and fits workspace files into a token budget.
        
        Ranks files by relevance:
        1. Error file (the file that caused the last compilation/runtime crash)
        2. Plan files (files the agent is scheduled to work on)
        3. Entry points / Key files (app.js, server.py, etc.)
        4. Query-relevant files (if they match keywords in user requests)
        
        Token budget manager ensures we only embed file contents up to max_tokens limit.
        """
        summary = self.summarize(idx)
        ranked_files = []
        
        clean_plan_files = [p.strip().lstrip("/") for p in (plan_files or [])]
        clean_error_file = error_file.strip().lstrip("/") if error_file else None
        if clean_error_file and "workspace/" in clean_error_file:
            clean_error_file = clean_error_file.split("workspace/", 1)[-1]
            
        for file_info in idx.files:
            rel_path = file_info.path
            score = 0
            
            if clean_error_file and (clean_error_file in rel_path or rel_path in clean_error_file):
                score += 1000
            if any(pf in rel_path or rel_path in pf for pf in clean_plan_files):
                score += 500
            if rel_path in idx.entry_points:
                score += 200
            if file_info.is_key_file:
                score += 100
            if query:
                keywords = [k.lower() for k in re.findall(r"\w+", query) if len(k) > 3]
                for kw in keywords:
                    if kw in rel_path.lower() or kw in file_info.file_type.lower():
                        score += 50
                        
            if score > 0:
                ranked_files.append((score, file_info))
                
        ranked_files.sort(key=lambda x: x[0], reverse=True)
        
        budget_chars = max_tokens * 4
        current_chars = len(summary)
        embedded_files = []
        
        for score, file_info in ranked_files:
            filepath = os.path.join(self.root, file_info.path)
            if not os.path.exists(filepath):
                continue
            if file_info.size > 100_000:
                continue
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue
                
            file_block = f"\n\n=========================================\nFILE: {file_info.path}\n=========================================\n{content}"
            block_len = len(file_block)
            
            if current_chars + block_len <= budget_chars:
                embedded_files.append(file_block)
                current_chars += block_len
                
        parts = [summary]
        if embedded_files:
            parts.append("\n\nRELEVANT FILE CONTENTS (EMBEDDED CONTEXT):")
            parts.extend(embedded_files)
            
        return "\n".join(parts)
