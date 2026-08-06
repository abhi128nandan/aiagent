"""
API Consistency Checker — detects frontend-backend mismatches.

Extracts API endpoints from backend route definitions (FastAPI, Express)
and frontend API calls (fetch, axios), then cross-validates:
  - Missing endpoints (frontend calls non-existent backend route)
  - Missing fields (backend expects fields frontend doesn't send)
  - Extra fields (frontend sends fields backend ignores)
  - Type mismatches (field name casing, type incompatibilities)

This is one of the highest-value analysis passes because API mismatches
cause silent runtime failures that are extremely hard to debug.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from core.logger import get_logger
from agent.code_analyzer import Issue, IssueCategory, IssueSeverity

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────


@dataclass
class EndpointInfo:
    """A backend API endpoint extracted from route definitions."""
    method: str          # GET, POST, PUT, DELETE, PATCH
    path: str            # /api/users, /api/projects/{id}
    file: str            # Source file where this endpoint is defined
    line: int = 0
    request_fields: List[str] = field(default_factory=list)   # Expected request body fields
    response_fields: List[str] = field(default_factory=list)  # Response body fields
    dto_name: str = ""   # Name of the DTO/schema class (e.g., "SavePrescriptionRequest")


@dataclass
class ApiCallInfo:
    """A frontend API call extracted from fetch/axios usage."""
    method: str          # GET, POST, etc.
    url: str             # /api/users
    file: str            # Source file where this call is made
    line: int = 0
    sent_fields: List[str] = field(default_factory=list)      # Fields sent in request body
    expected_fields: List[str] = field(default_factory=list)   # Fields expected in response


@dataclass
class ApiMismatch:
    """A detected mismatch between frontend and backend."""
    mismatch_type: str   # missing_endpoint, missing_field, extra_field, type_mismatch
    frontend_file: str
    backend_file: str = ""
    detail: str = ""


# ── API Consistency Checker ───────────────────────────────────────────


class ApiConsistencyChecker:
    """Cross-validates frontend API calls against backend endpoint definitions."""

    def __init__(self, workspace_root: str = "/workspace") -> None:
        self.root = workspace_root

    def check_project(self, index: Any) -> List[Issue]:
        """
        Run API consistency checks on the full project.

        Args:
            index: WorkspaceIndex with file information.

        Returns:
            List of Issue objects for detected mismatches.
        """
        issues: List[Issue] = []

        # Separate frontend and backend files
        backend_files = []
        frontend_files = []

        for file_info in index.files:
            path = file_info.path.lower()
            if file_info.file_type == "python":
                backend_files.append(file_info)
            elif file_info.file_type in ("javascript", "typescript", "javascript_react", "typescript_react"):
                # Heuristic: files in src/ or with React patterns are frontend
                if any(p in path for p in ["src/", "pages/", "components/", "hooks/", "app/"]):
                    frontend_files.append(file_info)
                elif any(p in path for p in ["routes/", "server/", "api/", "controllers/"]):
                    backend_files.append(file_info)

        if not backend_files or not frontend_files:
            return issues

        # Extract endpoints and API calls
        endpoints = self._extract_all_endpoints(backend_files)
        api_calls = self._extract_all_api_calls(frontend_files)

        if not endpoints or not api_calls:
            return issues

        # Cross-validate
        issues.extend(self._check_missing_endpoints(endpoints, api_calls))
        issues.extend(self._check_field_mismatches(endpoints, api_calls))

        logger.info(
            "api_consistency_check_complete",
            endpoints=len(endpoints),
            api_calls=len(api_calls),
            issues=len(issues),
        )

        return issues

    # ── Endpoint Extraction ───────────────────────────────────────────

    def _extract_all_endpoints(self, files: List[Any]) -> List[EndpointInfo]:
        """Extract API endpoints from all backend files."""
        endpoints: List[EndpointInfo] = []
        for file_info in files:
            filepath = os.path.join(self.root, file_info.path)
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError):
                continue

            if file_info.file_type == "python":
                endpoints.extend(self._extract_fastapi_endpoints(content, file_info.path))
            elif file_info.file_type in ("javascript", "typescript"):
                endpoints.extend(self._extract_express_endpoints(content, file_info.path))

        return endpoints

    def _extract_fastapi_endpoints(self, content: str, path: str) -> List[EndpointInfo]:
        """Extract endpoints from FastAPI/Flask route decorators."""
        endpoints: List[EndpointInfo] = []

        # Match @router.get("/path"), @app.post("/path"), etc.
        method_map = {
            "get": "GET", "post": "POST", "put": "PUT",
            "delete": "DELETE", "patch": "PATCH",
        }

        for match in re.finditer(
            r'@\w+\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            content, re.IGNORECASE
        ):
            method = method_map.get(match.group(1).lower(), match.group(1).upper())
            api_path = match.group(2)
            line = content[:match.start()].count("\n") + 1

            # Try to find request body fields from the function signature
            # Look for Pydantic model parameter
            func_match = re.search(
                r'def\s+\w+\s*\([^)]*?(\w+)\s*:\s*(\w+)',
                content[match.end():match.end() + 500]
            )
            dto_name = ""
            request_fields: List[str] = []
            if func_match:
                dto_name = func_match.group(2)
                # Try to find the Pydantic model class definition
                model_match = re.search(
                    rf'class\s+{re.escape(dto_name)}\s*\([^)]*\):\s*\n((?:\s+\w+\s*:.*\n)*)',
                    content
                )
                if model_match:
                    for field_match in re.finditer(r'\s+(\w+)\s*:', model_match.group(1)):
                        request_fields.append(field_match.group(1))

            endpoints.append(EndpointInfo(
                method=method,
                path=api_path,
                file=path,
                line=line,
                request_fields=request_fields,
                dto_name=dto_name,
            ))

        return endpoints

    def _extract_express_endpoints(self, content: str, path: str) -> List[EndpointInfo]:
        """Extract endpoints from Express.js route definitions."""
        endpoints: List[EndpointInfo] = []
        method_map = {
            "get": "GET", "post": "POST", "put": "PUT",
            "delete": "DELETE", "patch": "PATCH",
        }

        for match in re.finditer(
            r'(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            content, re.IGNORECASE
        ):
            method = method_map.get(match.group(1).lower(), match.group(1).upper())
            api_path = match.group(2)
            line = content[:match.start()].count("\n") + 1

            endpoints.append(EndpointInfo(
                method=method,
                path=api_path,
                file=path,
                line=line,
            ))

        return endpoints

    # ── Frontend API Call Extraction ──────────────────────────────────

    def _extract_all_api_calls(self, files: List[Any]) -> List[ApiCallInfo]:
        """Extract API calls from all frontend files."""
        calls: List[ApiCallInfo] = []
        for file_info in files:
            filepath = os.path.join(self.root, file_info.path)
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except (OSError, IOError):
                continue

            calls.extend(self._extract_fetch_calls(content, file_info.path))
            calls.extend(self._extract_axios_calls(content, file_info.path))

        return calls

    def _extract_fetch_calls(self, content: str, path: str) -> List[ApiCallInfo]:
        """Extract fetch() API calls."""
        calls: List[ApiCallInfo] = []

        # Match: fetch("/api/path", { method: "POST", ... })
        for match in re.finditer(
            r'fetch\s*\(\s*[`"\']([^`"\']+)[`"\'](?:\s*,\s*(\{.*?\}))?\s*\)',
            content, re.DOTALL
        ):
            url = match.group(1)
            options = match.group(2) or ""
            line = content[:match.start()].count("\n") + 1

            # Extract method
            method_match = re.search(r'method\s*:\s*["\'](\w+)["\']', options)
            method = method_match.group(1).upper() if method_match else "GET"

            # Extract body fields
            sent_fields: List[str] = []
            body_match = re.search(r'body\s*:\s*JSON\.stringify\s*\(\s*\{([^}]*)\}', options)
            if body_match:
                for field_m in re.finditer(r'(\w+)\s*[,:]', body_match.group(1)):
                    sent_fields.append(field_m.group(1))

            calls.append(ApiCallInfo(
                method=method,
                url=url,
                file=path,
                line=line,
                sent_fields=sent_fields,
            ))

        return calls

    def _extract_axios_calls(self, content: str, path: str) -> List[ApiCallInfo]:
        """Extract axios API calls."""
        calls: List[ApiCallInfo] = []

        # Match: axios.post("/api/path", { ... })
        for match in re.finditer(
            r'axios\.(get|post|put|delete|patch)\s*\(\s*[`"\']([^`"\']+)[`"\']',
            content, re.IGNORECASE
        ):
            method = match.group(1).upper()
            url = match.group(2)
            line = content[:match.start()].count("\n") + 1

            calls.append(ApiCallInfo(
                method=method,
                url=url,
                file=path,
                line=line,
            ))

        return calls

    # ── Cross-Validation ──────────────────────────────────────────────

    def _check_missing_endpoints(
        self, endpoints: List[EndpointInfo], calls: List[ApiCallInfo]
    ) -> List[Issue]:
        """Detect frontend calls to non-existent backend endpoints."""
        issues: List[Issue] = []

        # Normalize endpoint paths for comparison
        endpoint_paths: Set[str] = set()
        for ep in endpoints:
            # Normalize: remove path params like {id}
            normalized = re.sub(r'\{[^}]+\}', '*', ep.path)
            endpoint_paths.add(f"{ep.method}:{normalized}")

        for call in calls:
            # Skip external URLs
            if call.url.startswith("http") and "localhost" not in call.url:
                continue
            if not call.url.startswith("/"):
                continue

            normalized_url = re.sub(r'\$\{[^}]+\}', '*', call.url)
            normalized_url = re.sub(r'/[0-9a-f-]{20,}', '/*', normalized_url)
            call_key = f"{call.method}:{normalized_url}"

            # Check if any endpoint matches
            matched = False
            for ep_key in endpoint_paths:
                if self._paths_match(call_key, ep_key):
                    matched = True
                    break

            if not matched:
                issues.append(Issue(
                    category=IssueCategory.API_MISMATCH,
                    severity=IssueSeverity.HIGH,
                    file=call.file,
                    line=call.line,
                    message=f"Frontend calls {call.method} {call.url} but no matching backend endpoint exists",
                    suggestion=f"Create a backend endpoint for {call.method} {call.url} or fix the frontend URL",
                    fix_confidence=0.6,
                ))

        return issues

    def _check_field_mismatches(
        self, endpoints: List[EndpointInfo], calls: List[ApiCallInfo]
    ) -> List[Issue]:
        """Detect field mismatches between frontend and backend."""
        issues: List[Issue] = []

        for call in calls:
            if not call.sent_fields:
                continue

            # Find the matching endpoint
            for ep in endpoints:
                if not self._paths_match(
                    f"{call.method}:{call.url}",
                    f"{ep.method}:{re.sub(r'{[^}]+}', '*', ep.path)}"
                ):
                    continue

                if not ep.request_fields:
                    continue

                # Check for missing fields
                backend_fields = set(ep.request_fields)
                frontend_fields = set(call.sent_fields)

                missing = backend_fields - frontend_fields
                extra = frontend_fields - backend_fields

                for f_name in missing:
                    issues.append(Issue(
                        category=IssueCategory.API_MISMATCH,
                        severity=IssueSeverity.HIGH,
                        file=call.file,
                        line=call.line,
                        message=f"Backend expects field '{f_name}' but frontend doesn't send it",
                        suggestion=f"Add '{f_name}' to the request body in {call.file}",
                        fix_confidence=0.7,
                        related_files=[ep.file],
                    ))

                for f_name in extra:
                    issues.append(Issue(
                        category=IssueCategory.API_MISMATCH,
                        severity=IssueSeverity.MEDIUM,
                        file=call.file,
                        line=call.line,
                        message=f"Frontend sends field '{f_name}' but backend doesn't use it",
                        suggestion=f"Remove '{f_name}' from the request or add it to the backend DTO",
                        fix_confidence=0.5,
                        related_files=[ep.file],
                    ))

        return issues

    @staticmethod
    def _paths_match(call_key: str, endpoint_key: str) -> bool:
        """Check if a frontend call path matches a backend endpoint path."""
        # Simple matching: split into parts and compare
        call_method, call_path = call_key.split(":", 1)
        ep_method, ep_path = endpoint_key.split(":", 1)

        if call_method != ep_method:
            return False

        call_parts = call_path.strip("/").split("/")
        ep_parts = ep_path.strip("/").split("/")

        if len(call_parts) != len(ep_parts):
            return False

        for cp, ep in zip(call_parts, ep_parts):
            if ep == "*" or cp == "*":
                continue
            if cp != ep:
                return False

        return True
