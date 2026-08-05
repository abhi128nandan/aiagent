"""
LangGraph Subgraph for Autonomous Project Analysis and Code Improvement.

Orchestrates the 9-stage improvement cycle:
  1. scan_node       — runs WorkspaceIndexer to scan files
  2. build_kg_node    — builds KnowledgeGraph
  3. analyze_node     — runs AnalysisEngine to find security, performance, etc. issues
  4. prioritize_node  — ranks issues with IssuePrioritizer
  5. plan_fixes_node  — builds structured ImprovementPlan
  6. generate_fixes_node — generates safe code modifications with SafeCodeGenerator
  7. review_node      — AI Principal Code Reviewer self-critique pass
  8. apply_node       — applies changes (optionally, or returns for review)
  9. learn_node       — updates project MemoryManager with success/failure data
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import StateGraph, END

from core.logger import get_logger
from agent.workspace_indexer import WorkspaceIndexer
from agent.knowledge_graph import KnowledgeGraph
from agent.code_analyzer import AnalysisEngine
from agent.improvement_planner import IssuePrioritizer, ImprovementPlanner
from agent.safe_code_generator import SafeCodeGenerator
from agent.ai_reviewer import AICodeReviewer
from agent.memory import MemoryManager
from agent.llm import LLMFactory

logger = get_logger(__name__)


# ── State Definition ──────────────────────────────────────────────────


class AnalyzeState(TypedDict, total=False):
    session_id: str
    status: Literal['scanning', 'building_graph', 'analyzing', 'prioritizing', 'planning', 'generating_fixes', 'reviewing', 'applying', 'learning', 'done', 'error']
    workspace_path: str
    workspace_index: Optional[Dict[str, Any]]
    knowledge_graph: Optional[Dict[str, Any]]  # Serialized summary
    issues: List[Dict[str, Any]]
    plan: Optional[Dict[str, Any]]
    changes: List[Dict[str, Any]]
    applied_changes: List[Dict[str, Any]]
    errors: List[str]
    retries: int
    memory: Optional[Dict[str, Any]]


# ── Nodes ─────────────────────────────────────────────────────────────


async def scan_node(state: AnalyzeState) -> AnalyzeState:
    """Scan the workspace directory to list files and analyze properties."""
    session_id = state.get("session_id", "")
    path = state.get("workspace_path", "/workspace")
    logger.info("analyze_subgraph_scan_node_start", session_id=session_id, path=path)

    try:
        indexer = WorkspaceIndexer(path)
        index = indexer.index()

        # Simple conversion of dataclass to dict
        files_dict = []
        for f in index.files:
            syms = [
                {
                    "name": s.name,
                    "symbol_type": s.symbol_type,
                    "line_start": s.line_start,
                    "line_end": s.line_end,
                    "docstring": s.docstring,
                    "is_exported": s.is_exported,
                }
                for s in f.symbols
            ]
            files_dict.append({
                "path": f.path,
                "file_type": f.file_type,
                "size": f.size,
                "imports": f.imports,
                "exports": f.exports,
                "symbols": syms,
                "content_hash": f.content_hash,
                "is_key_file": f.is_key_file,
            })

        index_dict = {
            "project_type": index.project_type,
            "framework": index.framework,
            "file_count": index.file_count,
            "directory_count": index.directory_count,
            "dependencies": index.dependencies,
            "dev_dependencies": index.dev_dependencies,
            "key_files": index.key_files,
            "entry_points": index.entry_points,
            "tech_stack": index.tech_stack,
            "structure_tree": index.structure_tree,
            "files": files_dict,
        }

        # Send updates via websocket observability if needed
        return {
            **state,
            "status": "building_graph",
            "workspace_index": index_dict,
        }
    except Exception as e:
        logger.error("analyze_subgraph_scan_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Scan failed: {str(e)}"],
        }


async def build_graph_node(state: AnalyzeState) -> AnalyzeState:
    """Build the KnowledgeGraph using the workspace index."""
    session_id = state.get("session_id", "")
    logger.info("analyze_subgraph_build_graph_node_start", session_id=session_id)

    try:
        index_dict = state.get("workspace_index")
        if not index_dict:
            raise ValueError("No workspace index found in state")

        # Re-construct index dataclass shell for the KG builder
        from dataclasses import dataclass, field
        @dataclass
        class MockFile:
            path: str
            file_type: str
            size: int
            imports: List[str]
            exports: List[str]
            symbols: List[Any]
            content_hash: str
            is_key_file: bool

        @dataclass
        class MockIndex:
            files: List[MockFile]

        @dataclass
        class MockSymbol:
            name: str
            symbol_type: str
            line_start: int
            line_end: int
            docstring: str
            is_exported: bool
            decorators: List[str] = field(default_factory=list)
            bases: List[str] = field(default_factory=list)
            parameters: List[str] = field(default_factory=list)

        files = []
        for f in index_dict.get("files", []):
            syms = []
            for s in f.get("symbols", []):
                syms.append(MockSymbol(
                    name=s["name"],
                    symbol_type=s["symbol_type"],
                    line_start=s["line_start"],
                    line_end=s["line_end"],
                    docstring=s["docstring"],
                    is_exported=s["is_exported"],
                ))
            files.append(MockFile(
                path=f["path"],
                file_type=f["file_type"],
                size=f["size"],
                imports=f["imports"],
                exports=f["exports"],
                symbols=syms,
                content_hash=f["content_hash"],
                is_key_file=f["is_key_file"],
            ))

        mock_index = MockIndex(files=files)

        kg = KnowledgeGraph()
        kg.build_from_index(mock_index)

        return {
            **state,
            "status": "analyzing",
            "knowledge_graph": kg.to_dict(),
        }
    except Exception as e:
        logger.error("analyze_subgraph_build_graph_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Build graph failed: {str(e)}"],
        }


async def analyze_node(state: AnalyzeState) -> AnalyzeState:
    """Run all analysis passes to identify issues in the codebase."""
    session_id = state.get("session_id", "")
    logger.info("analyze_subgraph_analyze_node_start", session_id=session_id)

    try:
        path = state.get("workspace_path", "/workspace")
        index_dict = state.get("workspace_index")
        kg_dict = state.get("knowledge_graph")

        if not index_dict or not kg_dict:
            raise ValueError("Missing index or knowledge graph in state")

        # Instantiate builder shell again
        from dataclasses import dataclass
        @dataclass
        class MockFile:
            path: str
            file_type: str
            size: int
            imports: List[str]
            exports: List[str]

        @dataclass
        class MockIndex:
            files: List[MockFile]

        files = [MockFile(
            path=f["path"], file_type=f["file_type"], size=f["size"],
            imports=f["imports"], exports=f["exports"]
        ) for f in index_dict.get("files", [])]
        mock_index = MockIndex(files=files)

        kg = KnowledgeGraph.from_dict(kg_dict)
        # Restore mock graph structures for circular dependency checks
        import networkx as nx
        kg.graph = nx.DiGraph()
        for f in index_dict.get("files", []):
            file_key = f"file:{f['path']}"
            kg.graph.add_node(file_key, type="file")
            for imp in f.get("imports", []):
                # Search target
                target = None
                for tf in index_dict.get("files", []):
                    if imp in tf["path"] or tf["path"] in imp:
                        target = tf["path"]
                        break
                if target:
                    kg.graph.add_edge(file_key, f"file:{target}", relationship="imports")

        analyzer = AnalysisEngine(path)
        issues = analyzer.analyze_project(mock_index, kg)

        issues_dict = [issue.to_dict() for issue in issues]

        return {
            **state,
            "status": "prioritizing",
            "issues": issues_dict,
        }
    except Exception as e:
        logger.error("analyze_subgraph_analysis_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Analysis failed: {str(e)}"],
        }


async def prioritize_node(state: AnalyzeState) -> AnalyzeState:
    """Prioritize and score issues by severity, blast radius, and frequency."""
    session_id = state.get("session_id", "")
    logger.info("analyze_subgraph_prioritize_node_start", session_id=session_id)

    try:
        issues_dict = state.get("issues", [])
        kg_dict = state.get("knowledge_graph")

        if not issues_dict:
            # Short-circuit: no issues found
            return {
                **state,
                "status": "done",
            }

        # Convert issues back to dataclass objects for sorting
        from agent.code_analyzer import Issue, IssueCategory, IssueSeverity
        issues = []
        for i in issues_dict:
            issues.append(Issue(
                category=IssueCategory(i["category"]),
                severity=IssueSeverity(i["severity"]),
                file=i["file"],
                line=i.get("line", 0),
                message=i.get("message", ""),
                suggestion=i.get("suggestion", ""),
                fix_confidence=i.get("fix_confidence", 0.5),
            ))

        kg = KnowledgeGraph.from_dict(kg_dict) if kg_dict else None

        prioritizer = IssuePrioritizer()
        sorted_issues = prioritizer.prioritize(issues, kg)

        sorted_dict = [issue.to_dict() for issue in sorted_issues]

        return {
            **state,
            "status": "planning",
            "issues": sorted_dict,
        }
    except Exception as e:
        logger.error("analyze_subgraph_prioritize_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Prioritization failed: {str(e)}"],
        }


async def plan_fixes_node(state: AnalyzeState) -> AnalyzeState:
    """Create a structured plan for addressing the top prioritized issues."""
    session_id = state.get("session_id", "")
    logger.info("analyze_subgraph_plan_fixes_node_start", session_id=session_id)

    try:
        issues_dict = state.get("issues", [])
        kg_dict = state.get("knowledge_graph")

        if not issues_dict:
            return {**state, "status": "done"}

        from agent.code_analyzer import Issue, IssueCategory, IssueSeverity
        issues = []
        for i in issues_dict:
            issues.append(Issue(
                category=IssueCategory(i["category"]),
                severity=IssueSeverity(i["severity"]),
                file=i["file"],
                line=i.get("line", 0),
                message=i.get("message", ""),
                suggestion=i.get("suggestion", ""),
                fix_confidence=i.get("fix_confidence", 0.5),
            ))

        kg = KnowledgeGraph.from_dict(kg_dict) if kg_dict else None

        planner = ImprovementPlanner()
        plan = planner.create_plan(issues, kg, max_items=5)  # Limit to 5 issues per cycle

        return {
            **state,
            "status": "generating_fixes",
            "plan": plan.to_dict(),
        }
    except Exception as e:
        logger.error("analyze_subgraph_planning_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Planning failed: {str(e)}"],
        }


async def generate_fixes_node(state: AnalyzeState) -> AnalyzeState:
    """Generate safe code modifications using an LLM model."""
    session_id = state.get("session_id", "")
    logger.info("analyze_subgraph_generate_fixes_node_start", session_id=session_id)

    try:
        plan_dict = state.get("plan")
        issues_dict = state.get("issues", [])
        kg_dict = state.get("knowledge_graph")
        path = state.get("workspace_path", "/workspace")

        if not plan_dict or not issues_dict:
            return {**state, "status": "done"}

        # Extract targeted issues
        from agent.code_analyzer import Issue, IssueCategory, IssueSeverity
        issues_map = {}
        for i in issues_dict:
            key = f"{i['file']}:{i['category']}:{i.get('line', 0)}"
            issues_map[key] = Issue(
                category=IssueCategory(i["category"]),
                severity=IssueSeverity(i["severity"]),
                file=i["file"],
                line=i.get("line", 0),
                message=i.get("message", ""),
                suggestion=i.get("suggestion", ""),
                fix_confidence=i.get("fix_confidence", 0.5),
            )

        kg = KnowledgeGraph.from_dict(kg_dict) if kg_dict else None

        # Build LLM
        llm = LLMFactory().create()

        generator = SafeCodeGenerator(path)
        changes = []

        for item in plan_dict.get("items", []):
            # Resolve original issue object
            file = item["file"]
            desc = item["description"]
            # Look up issue by matching file name and category prefix
            target_issue = None
            for issue in issues_map.values():
                if issue.file == file and f"[{issue.category.value}]" in desc:
                    target_issue = issue
                    break

            if not target_issue:
                continue

            change = await generator.generate_fix(target_issue, kg, llm)
            if change:
                changes.append({
                    "file": change.file,
                    "original_content": change.original_content,
                    "new_content": change.new_content,
                    "diff_summary": change.diff_summary,
                    "change_type": change.change_type,
                    "validation_passed": change.validation_passed,
                })

        return {
            **state,
            "status": "reviewing" if changes else "done",
            "changes": changes,
        }
    except Exception as e:
        logger.error("analyze_subgraph_generation_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Fix generation failed: {str(e)}"],
        }


async def review_node(state: AnalyzeState) -> AnalyzeState:
    """AI self-review of proposed fixes before application."""
    session_id = state.get("session_id", "")
    logger.info("analyze_subgraph_review_node_start", session_id=session_id)

    try:
        changes = state.get("changes", [])
        issues_dict = state.get("issues", [])
        kg_dict = state.get("knowledge_graph")

        if not changes:
            return {**state, "status": "done"}

        # Build LLM
        llm = LLMFactory().create()
        reviewer = AICodeReviewer()
        kg = KnowledgeGraph.from_dict(kg_dict) if kg_dict else None

        # Convert issues to lookup map
        from agent.code_analyzer import Issue, IssueCategory, IssueSeverity
        issues_list = []
        for i in issues_dict:
            issues_list.append(Issue(
                category=IssueCategory(i["category"]),
                severity=IssueSeverity(i["severity"]),
                file=i["file"],
                line=i.get("line", 0),
                message=i.get("message", ""),
                suggestion=i.get("suggestion", ""),
                fix_confidence=i.get("fix_confidence", 0.5),
            ))

        approved_changes = []
        for change_dict in changes:
            # Map change back to mock shells
            from dataclasses import dataclass
            @dataclass
            class MockChange:
                file: str
                original_content: str
                new_content: str
                diff_summary: str
                change_type: str

            mock_change = MockChange(
                file=change_dict["file"],
                original_content=change_dict["original_content"],
                new_content=change_dict["new_content"],
                diff_summary=change_dict["diff_summary"],
                change_type=change_dict["change_type"],
            )

            # Find corresponding issue
            target_issue = None
            for issue in issues_list:
                if issue.file == change_dict["file"]:
                    target_issue = issue
                    break

            if not target_issue:
                continue

            review_res = await reviewer.review(mock_change, target_issue, kg, llm)
            if review_res.approved:
                change_dict["reviewed_approved"] = True
                approved_changes.append(change_dict)
            else:
                change_dict["reviewed_approved"] = False
                logger.warning(
                    "fix_rejected_by_reviewer",
                    file=change_dict["file"],
                    critique=review_res.critique,
                )

        return {
            **state,
            "status": "applying" if approved_changes else "done",
            "applied_changes": approved_changes,
        }
    except Exception as e:
        logger.error("analyze_subgraph_review_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Review failed: {str(e)}"],
        }


async def apply_node(state: AnalyzeState) -> AnalyzeState:
    """Commit approved changes to the workspace repository."""
    session_id = state.get("session_id", "")
    logger.info("analyze_subgraph_apply_node_start", session_id=session_id)

    try:
        changes = state.get("applied_changes", [])
        path = state.get("workspace_path", "/workspace")

        for change in changes:
            filepath = os.path.join(path, change["file"])
            # Ensure directories exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(change["new_content"])

            logger.info("fix_applied_to_workspace", file=change["file"])

        return {
            **state,
            "status": "learning",
        }
    except Exception as e:
        logger.error("analyze_subgraph_apply_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "error",
            "errors": state.get("errors", []) + [f"Apply changes failed: {str(e)}"],
        }


async def learn_node(state: AnalyzeState) -> AnalyzeState:
    """Record successes and failures in the project memory."""
    session_id = state.get("session_id", "")
    logger.info("analyze_subgraph_learn_node_start", session_id=session_id)

    try:
        changes = state.get("changes", [])
        applied_set = {c["file"] for c in state.get("applied_changes", [])}

        # Retrieve or instantiate memory manager
        memory_dict = state.get("memory") or {}
        # Simple local file-based persistent history if memory not initialized in graph state
        # In a real pipeline, the parent node loads/saves this.
        memory = MemoryManager()
        if memory_dict.get("fix_history"):
            for fh in memory_dict["fix_history"]:
                memory.record_fix(
                    file=fh["file"],
                    issue_category=fh["issue_category"],
                    issue_message=fh["issue_message"],
                    fix_diff=fh["fix_diff"],
                    success=fh["success"],
                    error_message=fh.get("error_message"),
                )

        for change in changes:
            success = change["file"] in applied_set
            memory.record_fix(
                file=change["file"],
                issue_category="code_improvement",
                issue_message=f"Auto fix verification pass",
                fix_diff=change["diff_summary"],
                success=success,
                error_message="Rejected by AI code reviewer" if not success else None,
            )

        return {
            **state,
            "status": "done",
            "memory": memory.to_dict(),
        }
    except Exception as e:
        logger.error("analyze_subgraph_learning_failed", session_id=session_id, error=str(e))
        return {
            **state,
            "status": "done",  # Fail-safe: don't fail the graph if learning fails
        }


# ── Subgraph Compilation ──────────────────────────────────────────────


def build_analyze_graph() -> StateGraph:
    """Build and compile the StateGraph for project analysis."""
    g = StateGraph(AnalyzeState)

    g.add_node("scan", scan_node)
    g.add_node("build_graph", build_graph_node)
    g.add_node("analyze", analyze_node)
    g.add_node("prioritize", prioritize_node)
    g.add_node("plan_fixes", plan_fixes_node)
    g.add_node("generate_fixes", generate_fixes_node)
    g.add_node("review", review_node)
    g.add_node("apply", apply_node)
    g.add_node("learn", learn_node)

    # Sequential edges
    g.add_edge("scan", "build_graph")
    g.add_edge("build_graph", "analyze")
    g.add_edge("analyze", "prioritize")

    # Routing decisions
    def route_after_prioritize(state: AnalyzeState) -> str:
        if state.get("status") == "done":
            return "done"
        if state.get("status") == "error":
            return "error"
        return "plan_fixes"

    g.add_conditional_edges("prioritize", route_after_prioritize, {
        "plan_fixes": "plan_fixes",
        "done": END,
        "error": END,
    })

    g.add_edge("plan_fixes", "generate_fixes")

    def route_after_generate(state: AnalyzeState) -> str:
        if state.get("status") == "done":
            return "done"
        if state.get("status") == "error":
            return "error"
        return "review"

    g.add_conditional_edges("generate_fixes", route_after_generate, {
        "review": "review",
        "done": END,
        "error": END,
    })

    def route_after_review(state: AnalyzeState) -> str:
        if state.get("status") == "done":
            return "done"
        if state.get("status") == "error":
            return "error"
        return "apply"

    g.add_conditional_edges("review", route_after_review, {
        "apply": "apply",
        "done": END,
        "error": END,
    })

    g.add_edge("apply", "learn")
    g.add_edge("learn", END)

    # Set entry point
    g.set_entry_point("scan")

    return g.compile()
