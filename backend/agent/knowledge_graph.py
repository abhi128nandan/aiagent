"""
Knowledge Graph Builder — maps relationships between all code entities.

Builds a directed graph of files, symbols, and their relationships
(imports, calls, inheritance) from the WorkspaceIndex.  Provides
queries like "what depends on this file?" and "what interfaces must
this file satisfy?" that feed the analysis engine and safe code
generator.

Uses NetworkX for in-memory graph operations — lightweight, no
external database required.  Serialisable to dict for LangGraph
state persistence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx  # type: ignore

from core.logger import get_logger

logger = get_logger(__name__)


# ── Data Structures ───────────────────────────────────────────────────


@dataclass
class SymbolNode:
    """A node representing a code symbol in the knowledge graph."""
    name: str
    symbol_type: str          # class, function, variable, interface, constant
    file: str                 # File this symbol is defined in
    line_start: int = 0
    line_end: int = 0
    docstring: str = ""
    is_exported: bool = False


@dataclass
class DependencyEdge:
    """An edge representing a relationship between two nodes."""
    source: str               # Source file or symbol
    target: str               # Target file or symbol
    relationship: str         # imports, calls, inherits, implements, exposes_api, consumes_api
    symbols: List[str] = field(default_factory=list)  # Specific imported symbols


@dataclass
class FileCluster:
    """A group of related files detected by the clustering algorithm."""
    name: str                 # e.g., "authentication", "api_routes", "data_models"
    files: List[str] = field(default_factory=list)
    description: str = ""


# ── Knowledge Graph ───────────────────────────────────────────────────


class KnowledgeGraph:
    """
    In-memory knowledge graph of a codebase.

    Nodes:
      - file:<path>    — a source file
      - sym:<file>::<name>  — a code symbol (class, function, etc.)

    Edges:
      - imports, calls, inherits, implements, exposes_api, consumes_api
    """

    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.file_nodes: Dict[str, Dict[str, Any]] = {}
        self.symbol_nodes: Dict[str, SymbolNode] = {}
        self.clusters: List[FileCluster] = []
        self.metadata: Dict[str, Any] = {}

    # ── Building ──────────────────────────────────────────────────────

    def build_from_index(self, index: Any) -> "KnowledgeGraph":
        """
        Build the knowledge graph from a WorkspaceIndex.

        Args:
            index: WorkspaceIndex with files, imports, exports, symbols.

        Returns:
            self for chaining.
        """
        # Phase 1: Add file nodes
        for file_info in index.files:
            file_key = f"file:{file_info.path}"
            self.graph.add_node(file_key, type="file", path=file_info.path,
                                file_type=file_info.file_type,
                                size=file_info.size)
            self.file_nodes[file_info.path] = {
                "file_type": file_info.file_type,
                "size": file_info.size,
                "imports": file_info.imports,
                "exports": file_info.exports,
                "hash": getattr(file_info, 'content_hash', ''),
            }

            # Phase 2: Add symbol nodes
            for sym in getattr(file_info, 'symbols', []):
                sym_key = f"sym:{file_info.path}::{sym.name}"
                self.graph.add_node(sym_key, type="symbol",
                                    name=sym.name,
                                    symbol_type=sym.symbol_type,
                                    file=file_info.path,
                                    line_start=sym.line_start,
                                    line_end=sym.line_end)
                self.symbol_nodes[sym_key] = SymbolNode(
                    name=sym.name,
                    symbol_type=sym.symbol_type,
                    file=file_info.path,
                    line_start=sym.line_start,
                    line_end=sym.line_end,
                    docstring=sym.docstring,
                    is_exported=sym.is_exported,
                )
                # Edge: file contains symbol
                self.graph.add_edge(file_key, sym_key, relationship="contains")

        # Phase 3: Resolve import edges between files
        self._resolve_imports(index)

        # Phase 4: Resolve inheritance edges
        self._resolve_inheritance(index)

        # Phase 5: Detect clusters
        self.clusters = self.detect_clusters()

        logger.info(
            "knowledge_graph_built",
            nodes=self.graph.number_of_nodes(),
            edges=self.graph.number_of_edges(),
            files=len(self.file_nodes),
            symbols=len(self.symbol_nodes),
            clusters=len(self.clusters),
        )

        return self

    def _resolve_imports(self, index: Any) -> None:
        """Create edges between files based on import statements."""
        # Build a lookup: module_name -> file_path
        module_lookup: Dict[str, str] = {}
        for file_info in index.files:
            path = file_info.path
            # Python: agent/graph.py -> agent.graph
            if path.endswith(".py"):
                module = path.replace("/", ".").replace("\\", ".").rstrip(".py")
                module_lookup[module] = path
                # Also register the last component
                parts = module.split(".")
                if parts:
                    module_lookup[parts[-1]] = path
            # JS/TS: src/components/App.tsx -> App, components/App
            else:
                basename = re.sub(r"\.(js|jsx|ts|tsx)$", "", path.split("/")[-1])
                module_lookup[basename] = path
                # Also register relative path without extension
                rel = re.sub(r"\.(js|jsx|ts|tsx)$", "", path)
                module_lookup[rel] = path

        for file_info in index.files:
            source_key = f"file:{file_info.path}"
            for imp in file_info.imports:
                # Try to resolve the import to a known file
                imp_clean = imp.lstrip(".")
                target_path = module_lookup.get(imp_clean)
                if not target_path:
                    # Try partial match
                    for mod_name, mod_path in module_lookup.items():
                        if imp_clean in mod_name or mod_name in imp_clean:
                            target_path = mod_path
                            break
                if target_path and target_path != file_info.path:
                    target_key = f"file:{target_path}"
                    if self.graph.has_node(target_key):
                        self.graph.add_edge(
                            source_key, target_key,
                            relationship="imports",
                            import_name=imp,
                        )

    def _resolve_inheritance(self, index: Any) -> None:
        """Create inheritance edges between classes."""
        # Build class name -> sym_key lookup
        class_lookup: Dict[str, str] = {}
        for sym_key, sym in self.symbol_nodes.items():
            if sym.symbol_type in ("class", "interface"):
                class_lookup[sym.name] = sym_key

        for file_info in index.files:
            for sym in getattr(file_info, 'symbols', []):
                if sym.symbol_type == "class" and getattr(sym, 'bases', []):
                    child_key = f"sym:{file_info.path}::{sym.name}"
                    for base_name in sym.bases:
                        parent_key = class_lookup.get(base_name)
                        if parent_key and parent_key != child_key:
                            self.graph.add_edge(
                                child_key, parent_key,
                                relationship="inherits",
                            )

    # ── Queries ───────────────────────────────────────────────────────

    def get_neighbors(self, file_path: str, depth: int = 1) -> List[str]:
        """Get files connected to the given file within N hops."""
        file_key = f"file:{file_path}"
        if not self.graph.has_node(file_key):
            return []

        visited: Set[str] = set()
        frontier = {file_key}
        for _ in range(depth):
            next_frontier: Set[str] = set()
            for node in frontier:
                for neighbor in list(self.graph.successors(node)) + list(self.graph.predecessors(node)):
                    if neighbor not in visited and neighbor.startswith("file:"):
                        next_frontier.add(neighbor)
                visited.update(frontier)
            frontier = next_frontier - visited

        visited.update(frontier)
        visited.discard(file_key)
        return [n.replace("file:", "") for n in visited if n.startswith("file:")]

    def get_reverse_dependencies(self, file_path: str) -> List[str]:
        """Get all files that import/depend on the given file."""
        file_key = f"file:{file_path}"
        if not self.graph.has_node(file_key):
            return []

        dependents = []
        for predecessor in self.graph.predecessors(file_key):
            if predecessor.startswith("file:"):
                edge_data = self.graph.get_edge_data(predecessor, file_key, {})
                if edge_data.get("relationship") == "imports":
                    dependents.append(predecessor.replace("file:", ""))
        return dependents

    def get_symbols_in_file(self, file_path: str) -> List[SymbolNode]:
        """Get all symbols defined in a file."""
        prefix = f"sym:{file_path}::"
        return [
            sym for key, sym in self.symbol_nodes.items()
            if key.startswith(prefix)
        ]

    def get_interfaces_used_by(self, file_path: str) -> List[SymbolNode]:
        """Get interfaces/classes that this file's symbols inherit from."""
        interfaces = []
        for sym_key, sym in self.symbol_nodes.items():
            if sym.file == file_path:
                # Look for inheritance edges
                for _, target in self.graph.out_edges(sym_key):
                    target_sym = self.symbol_nodes.get(target)
                    if target_sym and target_sym.symbol_type in ("class", "interface"):
                        interfaces.append(target_sym)
        return interfaces

    def get_file_importance(self, file_path: str) -> int:
        """Calculate how important a file is based on how many things depend on it."""
        return len(self.get_reverse_dependencies(file_path))

    def detect_clusters(self) -> List[FileCluster]:
        """Group related files into functional clusters using shared imports."""
        file_keys = [n for n in self.graph.nodes if n.startswith("file:")]
        if len(file_keys) < 2:
            return []

        # Build undirected file-file graph for community detection
        file_graph = nx.Graph()
        for fk in file_keys:
            file_graph.add_node(fk)

        for fk in file_keys:
            for neighbor in self.graph.successors(fk):
                if neighbor.startswith("file:") and neighbor in file_keys:
                    file_graph.add_edge(fk, neighbor)
            for predecessor in self.graph.predecessors(fk):
                if predecessor.startswith("file:") and predecessor in file_keys:
                    file_graph.add_edge(fk, predecessor)

        # Use connected components as clusters (simple, deterministic)
        clusters = []
        for i, component in enumerate(nx.connected_components(file_graph)):
            files = sorted(n.replace("file:", "") for n in component)
            if len(files) < 2:
                continue

            # Name the cluster based on common directory prefix
            common_prefix = _common_directory(files)
            cluster_name = common_prefix or f"cluster_{i}"

            clusters.append(FileCluster(
                name=cluster_name,
                files=files,
                description=f"{len(files)} related files",
            ))

        return clusters

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the knowledge graph to a dict for LangGraph state."""
        return {
            "nodes": len(self.graph.nodes),
            "edges": len(self.graph.edges),
            "files": list(self.file_nodes.keys()),
            "symbols": {
                k: {
                    "name": v.name,
                    "type": v.symbol_type,
                    "file": v.file,
                    "exported": v.is_exported,
                }
                for k, v in self.symbol_nodes.items()
            },
            "clusters": [
                {"name": c.name, "files": c.files, "description": c.description}
                for c in self.clusters
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGraph":
        """Deserialize a knowledge graph from a dict (lightweight — no full graph rebuild)."""
        kg = cls()
        kg.metadata = data.get("metadata", {})
        for cluster_data in data.get("clusters", []):
            kg.clusters.append(FileCluster(**cluster_data))
        return kg

    def summary(self) -> str:
        """Human-readable summary for debugging and logging."""
        lines = [
            f"Knowledge Graph: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges",
            f"  Files: {len(self.file_nodes)}",
            f"  Symbols: {len(self.symbol_nodes)}",
            f"  Clusters: {len(self.clusters)}",
        ]
        for cluster in self.clusters[:5]:
            lines.append(f"    [{cluster.name}]: {', '.join(cluster.files[:5])}")
        return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────


def _common_directory(paths: List[str]) -> str:
    """Find the common directory prefix of a list of file paths."""
    if not paths:
        return ""
    parts_list = [p.split("/") for p in paths]
    common = []
    for level_parts in zip(*parts_list):
        if len(set(level_parts)) == 1:
            common.append(level_parts[0])
        else:
            break
    return "/".join(common) if common else ""
