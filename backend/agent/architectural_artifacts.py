from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal, Dict, Any
import re

class ReactFlowGraph(BaseModel):
    nodes: List[Dict[str, Any]] = Field(
        ..., 
        description="List of React Flow nodes. Each must have 'id' (str) and 'data' (dict) with at least a 'label' string."
    )
    edges: List[Dict[str, Any]] = Field(
        ..., 
        description="List of React Flow edges. Each must have 'id', 'source', and 'target' (all str) matching node ids."
    )

    @model_validator(mode='after')
    def validate_graph(self):
        node_ids = set()
        for node in self.nodes:
            if 'id' not in node or not isinstance(node['id'], str):
                raise ValueError(f"Node missing string 'id': {node}")
            if 'data' not in node or not isinstance(node['data'], dict):
                raise ValueError(f"Node missing dictionary 'data': {node}")
            node_ids.add(node['id'])

        for edge in self.edges:
            if 'id' not in edge or not isinstance(edge['id'], str):
                raise ValueError(f"Edge missing string 'id': {edge}")
            if 'source' not in edge or 'target' not in edge:
                raise ValueError(f"Edge missing 'source' or 'target': {edge}")
            if edge['source'] not in node_ids:
                raise ValueError(f"Edge source '{edge['source']}' does not match any node id")
            if edge['target'] not in node_ids:
                raise ValueError(f"Edge target '{edge['target']}' does not match any node id")
        return self


class ArchitecturalArtifacts(BaseModel):
    system_diagram: ReactFlowGraph = Field(..., description="High-level container graph")
    component_diagram: ReactFlowGraph = Field(..., description="Component interaction graph")
    data_flow_diagram: ReactFlowGraph = Field(..., description="Data flow graph")
    sequence_diagrams: List[ReactFlowGraph] = Field(default_factory=list, description="Sequence represented as flowchart")
    deployment_diagram: ReactFlowGraph = Field(..., description="Runtime deployment architecture")


class ArchitectureDecisionRecord(BaseModel):
    id: str = Field(..., description="Unique identifier (ADR-001, ADR-002, ...)")
    title: str = Field(..., description="Short decision title")
    status: Literal['Proposed', 'Accepted', 'Superseded'] = 'Proposed'
    context: str = Field(..., description="Why this decision was needed")
    decision: str = Field(..., description="What was decided")
    consequences: str = Field(..., description="Positive and negative implications")
    alternatives: List[str] = Field(default_factory=list, description="Other options considered")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    updated_at: Optional[str] = None
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        if not re.match(r"^ADR-\d{3}$", v):
            raise ValueError("ADR id must follow the pattern 'ADR-\\d{3}' (e.g. ADR-001)")
        return v


class ArchitecturalPlan(BaseModel):
    architecture_generated_at: str = Field(..., description="ISO 8601 timestamp")
    architectural_artifacts: ArchitecturalArtifacts
    architecture_decisions: List[ArchitectureDecisionRecord] = Field(default_factory=list)
    architecture_approved: bool = False
    architecture_revision: int = 1
    architecture_feedback: str = ""
    tech_stack_summary: str = ""
    estimated_complexity: Literal['Low', 'Medium', 'High', 'VeryHigh'] = 'Medium'
