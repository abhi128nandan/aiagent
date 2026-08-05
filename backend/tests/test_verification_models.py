import pytest
from pydantic import ValidationError
from agent.architectural_artifacts import ArchitecturalArtifacts, ArchitectureDecisionRecord, ArchitecturalPlan
from agent.stage_checkpoint import StageCheckpoint, VerificationResult, VerificationMode
from datetime import datetime

# Sample valid ReactFlowGraph for testing
VALID_GRAPH = {
    "nodes": [{"id": "A", "data": {"label": "Node A"}}, {"id": "B", "data": {"label": "Node B"}}],
    "edges": [{"id": "e1", "source": "A", "target": "B"}]
}

INVALID_GRAPH = {
    "nodes": [{"id": 123, "data": {"label": "Node A"}}],  # id must be string
    "edges": []
}

def test_architectural_artifacts_valid():
    artifacts = ArchitecturalArtifacts(
        system_diagram=VALID_GRAPH,
        component_diagram=VALID_GRAPH,
        data_flow_diagram=VALID_GRAPH,
        sequence_diagrams=[VALID_GRAPH],
        deployment_diagram=VALID_GRAPH
    )
    assert len(artifacts.system_diagram.nodes) == 2
    assert len(artifacts.sequence_diagrams) == 1

def test_architectural_artifacts_invalid_graph():
    with pytest.raises(ValidationError) as excinfo:
        ArchitecturalArtifacts(
            system_diagram=INVALID_GRAPH,
            component_diagram=VALID_GRAPH,
            data_flow_diagram=VALID_GRAPH,
            sequence_diagrams=[VALID_GRAPH],
            deployment_diagram=VALID_GRAPH
        )
    assert "validation error" in str(excinfo.value).lower()

def test_architectural_artifacts_empty_sequences_allowed():
    artifacts = ArchitecturalArtifacts(
        system_diagram=VALID_GRAPH,
        component_diagram=VALID_GRAPH,
        data_flow_diagram=VALID_GRAPH,
        sequence_diagrams=[],
        deployment_diagram=VALID_GRAPH
    )
    assert len(artifacts.sequence_diagrams) == 0

def test_adr_valid():
    adr = ArchitectureDecisionRecord(
        id="ADR-001",
        title="Use PostgreSQL for persistent storage",
        status="Accepted",
        context="We need to store relational data.",
        decision="We will use PostgreSQL.",
        consequences="Relational schema migrations are required.",
        alternatives=["MongoDB", "SQLite"],
        created_at=datetime.utcnow().isoformat()
    )
    assert adr.id == "ADR-001"
    assert adr.status == "Accepted"

def test_adr_invalid_id():
    with pytest.raises(ValidationError) as excinfo:
        ArchitectureDecisionRecord(
            id="ADR-abc",
            title="Use PostgreSQL",
            status="Accepted",
            context="Context",
            decision="Decision",
            consequences="Consequences",
            created_at=datetime.utcnow().isoformat()
        )
    assert "ADR id must follow the pattern" in str(excinfo.value)

def test_stage_checkpoint_lifecycle():
    checkpoint = StageCheckpoint(stage_name="bootstrap")
    assert checkpoint.verification_status == "Pending"
    assert checkpoint.retry_count == 0
    
    checkpoint.increment_retry()
    assert checkpoint.retry_count == 1
    assert checkpoint.verification_timestamp is not None
    
    checkpoint.update_status("Pass", {"some_detail": "all fields OK"})
    assert checkpoint.verification_status == "Pass"
    assert checkpoint.verification_details["some_detail"] == "all fields OK"
    
    checkpoint.reset()
    assert checkpoint.retry_count == 0
