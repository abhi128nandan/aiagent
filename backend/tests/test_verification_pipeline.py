import pytest
from unittest.mock import AsyncMock, patch
from agent.state_manager import create_initial_state
from agent.stage_checkpoint import VerificationMode
from agent.checkpoint_manager import CheckpointManager
from agent.routing_decision_engine import RoutingDecisionEngine
from agent.graph import (
    route_after_bootstrap,
    route_after_architecture,
    route_after_research,
    route_after_setup,
    route_after_judge,
    plan_bootstrap_node_wrapped,
    architecture_plan_node_wrapped
)

@pytest.mark.anyio
@patch("agent.graph.plan_bootstrap_node", new_callable=AsyncMock)
async def test_bootstrap_node_wrapped_success(mock_bootstrap):
    # Setup mock bootstrap node to return a valid plan
    state = create_initial_state("session-123")
    state["plan"] = '{"project": "test", "description": "desc", "tech_stack": {}, "environment": "env", "template_selected": "react-vite"}'
    mock_bootstrap.return_value = state

    # Execute wrapped node
    final_state = await plan_bootstrap_node_wrapped(state)

    # Check verification status and next status
    assert final_state["stage_checkpoints"]["bootstrap"].verification_status == "Pass"
    assert final_state["status"] == "architecture"

@pytest.mark.anyio
@patch("agent.graph.plan_bootstrap_node", new_callable=AsyncMock)
async def test_bootstrap_node_wrapped_fail_retry(mock_bootstrap):
    # Setup mock bootstrap node to return a plan with interactive scaffold command (severity Error)
    state = create_initial_state("session-123")
    state["plan"] = '{"project": "test", "description": "desc", "tech_stack": {}, "environment": "env", "template_selected": "invalid-template"}'
    mock_bootstrap.return_value = state

    # Execute wrapped node
    final_state = await plan_bootstrap_node_wrapped(state)

    # Check status remains 'plan' for retry (not escalated to error)
    assert final_state["stage_checkpoints"]["bootstrap"].verification_status == "Fail"
    assert final_state["stage_checkpoints"]["bootstrap"].retry_count == 1
    assert final_state["status"] == "plan"

@pytest.mark.anyio
@patch("agent.graph.plan_bootstrap_node", new_callable=AsyncMock)
async def test_bootstrap_node_wrapped_fail_critical(mock_bootstrap):
    # Setup mock bootstrap node to return invalid JSON (severity Critical)
    state = create_initial_state("session-123")
    state["plan"] = "{invalid"
    mock_bootstrap.return_value = state

    # Execute wrapped node
    final_state = await plan_bootstrap_node_wrapped(state)

    # Check status becomes 'error' immediately for critical failures
    assert final_state["stage_checkpoints"]["bootstrap"].verification_status == "Fail"
    assert final_state["status"] == "error"


def test_routing_strict_vs_permissive():
    # Setup failing result
    from agent.stage_checkpoint import VerificationResult, StageCheckpoint
    
    checkpoint = StageCheckpoint(
        stage_name="bootstrap",
        verification_status="Fail",
        retry_count=3, # Max retries reached
        max_retries=3
    )
    
    result = VerificationResult(
        passed=False,
        stage="bootstrap",
        severity="Error",
        errors=["Required fields missing"],
        checkpoint_data=checkpoint
    )

    # 1. Strict mode: should escalate to 'error'
    state_strict = {"verification_mode": VerificationMode.Strict, "verification_enabled": True}
    next_node = RoutingDecisionEngine.route("bootstrap", result, state_strict)
    assert next_node == "error"

    # 2. Permissive mode: should proceed to 'architecture_plan' despite failure
    state_permissive = {"verification_mode": VerificationMode.Permissive, "verification_enabled": True}
    next_node = RoutingDecisionEngine.route("bootstrap", result, state_permissive)
    assert next_node == "architecture_plan"

    # 3. Disabled: should proceed
    state_disabled = {"verification_mode": VerificationMode.Disabled, "verification_enabled": True}
    next_node = RoutingDecisionEngine.route("bootstrap", result, state_disabled)
    assert next_node == "architecture_plan"

def test_route_after_judge_loop():
    # 1. approved plan -> supervisor
    state_approved = {"plan_approved": True, "judge_attempts": 1}
    assert route_after_judge(state_approved) == "supervisor"

    # 2. rejected plan, attempts < 3 -> plan_refine
    state_rejected = {"plan_approved": False, "judge_attempts": 2}
    assert route_after_judge(state_rejected) == "plan_refine"

    # 3. rejected plan, attempts >= 3 -> architecture_plan (replanning)
    state_failed_loop = {"plan_approved": False, "judge_attempts": 3}
    assert route_after_judge(state_failed_loop) == "architecture_plan"

@pytest.mark.anyio
@patch("agent.graph.architecture_plan_node", new_callable=AsyncMock)
async def test_architecture_node_wrapped_success(mock_arch):
    from agent.architectural_artifacts import ArchitecturalPlan, ArchitecturalArtifacts
    from agent.adr_manager import ADRManager
    
    # Setup mock architecture plan
    state = create_initial_state("session-123")
    valid_graph = {
        "nodes": [{"id": "A", "data": {"label": "Node A"}}, {"id": "B", "data": {"label": "Node B"}}],
        "edges": [{"id": "e1", "source": "A", "target": "B"}]
    }
    artifacts = ArchitecturalArtifacts(
        system_diagram=valid_graph,
        component_diagram=valid_graph,
        data_flow_diagram=valid_graph,
        sequence_diagrams=[valid_graph],
        deployment_diagram=valid_graph
    )
    adr = ADRManager.generate_tech_stack_adr({"frontend": "React"})
    plan = ArchitecturalPlan(
        architecture_generated_at="2026-06-16T12:00:00Z",
        architectural_artifacts=artifacts,
        architecture_decisions=[adr],
        architecture_approved=True,
        architecture_revision=1,
        tech_stack_summary="React, FastAPI",
        estimated_complexity="Medium"
    )
    state["architectural_plan"] = plan
    mock_arch.return_value = state

    # Execute wrapped node
    final_state = await architecture_plan_node_wrapped(state)

    # Check status and verification status
    assert final_state["stage_checkpoints"]["architecture"].verification_status == "Pass"
    assert final_state["status"] == "research"

@pytest.mark.anyio
@patch("agent.graph.architecture_plan_node", new_callable=AsyncMock)
async def test_architecture_node_wrapped_fail(mock_arch):
    # Setup mock architecture plan with missing diagrams
    state = create_initial_state("session-123")
    state["architectural_plan"] = None
    mock_arch.return_value = state

    # Execute wrapped node
    final_state = await architecture_plan_node_wrapped(state)

    # Check status and verification status
    assert final_state["stage_checkpoints"]["architecture"].verification_status == "Fail"
    assert final_state["status"] == "error" # Critical failure immediately escalates to error


@pytest.mark.anyio
@patch("agent.graph.plan_bootstrap_node", new_callable=AsyncMock)
async def test_bootstrap_node_clears_node_exception(mock_plan):
    state = create_initial_state("session-123")
    state["node_exception"] = {"type": "TemplateNotFoundError", "message": "Test error"}
    state["plan"] = '{"project": "test", "description": "desc", "tech_stack": {"frontend": "react", "backend": "none", "database": "none", "language": "typescript"}, "environment": {"runtime": ["node"]}, "template_selected": "react-vite", "run_command": "npm run dev", "steps": []}'
    
    mock_plan.return_value = state.copy()
    
    final_state = await plan_bootstrap_node_wrapped(state)
    assert "node_exception" not in final_state


