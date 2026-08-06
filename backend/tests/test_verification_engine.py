import pytest
from agent.checkpoint_manager import CheckpointManager
from agent.stage_verifier import StageVerifier
from agent.verification_rules import VerificationRuleEngine
from agent.architectural_artifacts import ArchitecturalPlan, ArchitecturalArtifacts
from agent.stage_checkpoint import VerificationMode

VALID_PLAN_JSON = """{
    "project": "Test Project",
    "description": "A test project description that is long enough.",
    "tech_stack": {
        "frontend": "React",
        "backend": "FastAPI"
    },
    "environment": "Docker",
    "template_selected": "react-vite"
}"""

INVALID_PLAN_JSON = "{invalid json"

VALID_MERMAID = "graph TD\n    A --> B"
INVALID_MERMAID = "invalid_mermaid"

def test_checkpoint_manager_initialization():
    cps = CheckpointManager.create_checkpoints()
    assert len(cps) == 7
    assert cps["bootstrap"].verification_status == "Pending"
    assert cps["bootstrap"].retry_count == 0

def test_bootstrap_verification_passed():
    state = {
        "plan": VALID_PLAN_JSON,
        "stage_checkpoints": CheckpointManager.create_checkpoints(),
        "verification_history": []
    }
    verifier = StageVerifier()
    res = verifier.verify("bootstrap", state)
    
    assert res.passed is True
    assert state["stage_checkpoints"]["bootstrap"].verification_status == "Pass"
    assert state["stage_checkpoints"]["bootstrap"].retry_count == 0

def test_bootstrap_verification_failed():
    state = {
        "plan": INVALID_PLAN_JSON,
        "stage_checkpoints": CheckpointManager.create_checkpoints(),
        "verification_history": []
    }
    verifier = StageVerifier()
    res = verifier.verify("bootstrap", state)
    
    assert res.passed is False
    assert state["stage_checkpoints"]["bootstrap"].verification_status == "Fail"
    assert state["stage_checkpoints"]["bootstrap"].retry_count == 1
    assert len(res.errors) > 0

def test_command_injection_detection():
    # Test safe command
    state_safe = {
        "pending_actions": [{"type": "run", "command": "npm run dev"}],
        "execution_results": [],
        "stage_checkpoints": CheckpointManager.create_checkpoints(),
        "verification_history": []
    }
    verifier = StageVerifier()
    res_safe = verifier.verify("execute", state_safe)
    # Even if other execute checks fail, check that no command injection error was raised
    assert not any("command injection" in err.lower() for err in res_safe.errors)

    # Test unsafe command
    state_unsafe = {
        "pending_actions": [{"type": "run", "command": "npm run dev; rm -rf /"}],
        "execution_results": [],
        "stage_checkpoints": CheckpointManager.create_checkpoints(),
        "verification_history": []
    }
    res_unsafe = verifier.verify("execute", state_unsafe)
    assert res_unsafe.passed is False
    assert res_unsafe.severity == "Critical"
    assert any("command injection" in err.lower() for err in res_unsafe.errors)

def test_checkpoint_summary():
    state = {
        "stage_checkpoints": CheckpointManager.create_checkpoints()
    }
    summary = CheckpointManager.get_checkpoint_summary(state)
    assert "bootstrap" in summary and "Pending" in summary
    assert "execute" in summary and "Pending" in summary

    CheckpointManager.update_checkpoint("bootstrap", "Pass", state)
    summary_updated = CheckpointManager.get_checkpoint_summary(state)
    assert "bootstrap" in summary_updated and "Pass" in summary_updated

