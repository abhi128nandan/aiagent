"""
Unit test suite for the Autonomous Code Analysis & Improvement Engine.
"""
from __future__ import annotations

import os
import tempfile
import pytest
from dataclasses import dataclass, field
from typing import List

from agent.workspace_indexer import WorkspaceIndexer, SymbolInfo, compute_file_hash
from agent.knowledge_graph import KnowledgeGraph, SymbolNode
from agent.code_analyzer import AnalysisEngine, IssueCategory, IssueSeverity
from agent.api_consistency_checker import ApiConsistencyChecker
from agent.improvement_planner import IssuePrioritizer, ImprovementPlanner
from agent.ai_reviewer import AICodeReviewer


# ── Component 1: Workspace Indexer AST & Hash Tests ──────────────────

def test_file_hash_computation():
    content = "print('hello world')"
    h1 = compute_file_hash(content)
    h2 = compute_file_hash(content)
    h3 = compute_file_hash(content + "\n")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 16


def test_python_symbol_extraction():
    content = """
import os

MY_CONSTANT = 42

def my_func(a, b):
    \"\"\"This is a docstring.\"\"\"
    return a + b

class MyClass:
    def __init__(self):
        pass
"""
    indexer = WorkspaceIndexer("/tmp")
    symbols = indexer._extract_python_symbols(content)

    func_sym = [s for s in symbols if s.name == "my_func"]
    class_sym = [s for s in symbols if s.name == "MyClass"]
    const_sym = [s for s in symbols if s.name == "MY_CONSTANT"]

    assert len(func_sym) == 1
    assert func_sym[0].symbol_type == "function"
    assert "This is a docstring." in func_sym[0].docstring
    assert "a" in func_sym[0].parameters

    assert len(class_sym) == 1
    assert class_sym[0].symbol_type == "class"

    assert len(const_sym) == 1
    assert const_sym[0].symbol_type == "constant"


def test_js_symbol_extraction():
    content = """
export function calculateSum(a, b) {
    return a + b;
}

export const processData = async (data) => {
    return data;
}

class UserService extends BaseService {
    getUser() {}
}

export interface User {
    id: string;
}
"""
    indexer = WorkspaceIndexer("/tmp")
    symbols = indexer._extract_js_symbols(content)

    func_sym = [s for s in symbols if s.name == "calculateSum"]
    arrow_sym = [s for s in symbols if s.name == "processData"]
    class_sym = [s for s in symbols if s.name == "UserService"]
    iface_sym = [s for s in symbols if s.name == "User"]

    assert len(func_sym) == 1
    assert func_sym[0].symbol_type == "function"
    assert func_sym[0].is_exported is True

    assert len(arrow_sym) == 1
    assert arrow_sym[0].symbol_type == "function"
    assert arrow_sym[0].is_async is True

    assert len(class_sym) == 1
    assert class_sym[0].symbol_type == "class"
    assert "BaseService" in class_sym[0].bases

    assert len(iface_sym) == 1
    assert iface_sym[0].symbol_type == "interface"


# ── Component 2: Knowledge Graph Tests ────────────────────────────────

@dataclass
class MockFileInfo:
    path: str
    file_type: str
    size: int = 1000
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    symbols: List[SymbolInfo] = field(default_factory=list)
    content_hash: str = "abc"
    is_key_file: bool = False

@dataclass
class MockIndex:
    files: List[MockFileInfo]


def test_knowledge_graph_builder_and_queries():
    f1 = MockFileInfo(
        path="utils.py",
        file_type="python",
        symbols=[SymbolInfo(name="helper", symbol_type="function")]
    )
    f2 = MockFileInfo(
        path="main.py",
        file_type="python",
        imports=["utils"],
        symbols=[SymbolInfo(name="run", symbol_type="function")]
    )

    index = MockIndex(files=[f1, f2])
    kg = KnowledgeGraph()
    kg.build_from_index(index)

    # Verify nodes
    assert kg.graph.has_node("file:utils.py")
    assert kg.graph.has_node("file:main.py")
    assert kg.graph.has_node("sym:utils.py::helper")

    # Verify dependencies
    deps = kg.get_reverse_dependencies("utils.py")
    assert "main.py" in deps

    # Neighbors within 1 hop
    neighbors = kg.get_neighbors("main.py", depth=1)
    assert "utils.py" in neighbors

    # Symbols defined in utils
    syms = kg.get_symbols_in_file("utils.py")
    assert len(syms) == 1
    assert syms[0].name == "helper"


# ── Component 3: Analysis Engine Tests ────────────────────────────────

def test_analysis_passes():
    analyzer = AnalysisEngine("/tmp")

    # Syntax test
    bad_syntax = "def foo("
    issues = analyzer.pass_syntax("foo.py", bad_syntax)
    assert len(issues) == 1
    assert issues[0].category == IssueCategory.SYNTAX

    # Security test
    insecure = "db_password = 'super_secret_password_123'"
    issues = analyzer.pass_security("config.py", insecure)
    assert len(issues) >= 1
    assert any(i.category == IssueCategory.SECURITY for i in issues)

    # Performance test
    slow = """
async def handler():
    time.sleep(10)
"""
    issues = analyzer.pass_performance("app.py", slow)
    assert len(issues) >= 1
    assert any(i.category == IssueCategory.PERFORMANCE for i in issues)

    # Code smell test
    smell = """
try:
    do_something()
except:
    pass
"""
    issues = analyzer.pass_code_smells("smelly.py", smell)
    assert len(issues) >= 1
    assert any("Bare except" in i.message for i in issues)


# ── Component 3b: API Consistency Checker Tests ──────────────────────

def test_api_consistency_checker():
    # Setup checker
    checker = ApiConsistencyChecker("/tmp")

    # Mock fastapi route file content
    fastapi_content = """
@router.post("/api/prescriptions")
def save_prescription(payload: SavePrescriptionRequest):
    pass
"""
    # Mock frontend code content
    frontend_content = """
fetch("/api/prescriptions", {
    method: "POST",
    body: JSON.stringify({
        patient_id: 123
    })
})
"""

    endpoints = checker._extract_fastapi_endpoints(fastapi_content, "routes.py")
    calls = checker._extract_fetch_calls(frontend_content, "page.tsx")

    assert len(endpoints) == 1
    assert endpoints[0].path == "/api/prescriptions"
    assert endpoints[0].method == "POST"

    assert len(calls) == 1
    assert calls[0].url == "/api/prescriptions"
    assert calls[0].method == "POST"
    assert "patient_id" in calls[0].sent_fields


# ── Component 4: Issue Prioritizer & Planner Tests ────────────────────

def test_issue_prioritizer_and_planner():
    from agent.code_analyzer import Issue
    i1 = Issue(
        category=IssueCategory.SECURITY,
        severity=IssueSeverity.CRITICAL,
        file="auth.py",
        message="SQL injection"
    )
    i2 = Issue(
        category=IssueCategory.CODE_SMELL,
        severity=IssueSeverity.LOW,
        file="helper.py",
        message="Too long"
    )

    prioritizer = IssuePrioritizer()
    sorted_issues = prioritizer.prioritize([i2, i1])

    # i1 is critical security, i2 is low smell, so i1 should be first
    assert sorted_issues[0].category == IssueCategory.SECURITY

    planner = ImprovementPlanner()
    plan = planner.create_plan(sorted_issues)
    assert plan.planned_issues == 2
    assert plan.items[0].file == "auth.py"
    assert plan.items[1].file == "helper.py"
