from typing import Dict, Any, Optional
from agent.stage_checkpoint import StageCheckpoint, VerificationResult, VerificationMode
from agent.checkpoint_manager import CheckpointManager
from core.logger import get_logger
from agent.state import AgentState

logger = get_logger(__name__)

class RoutingDecisionEngine:
    STAGE_TO_NODE = {
        "bootstrap": "plan_bootstrap",
        "architecture": "architecture_plan",
        "research": "research",
        "setup": "setup_environment",
        "detail": "plan_refine",
        "judge": "judge",
        "execute": "execute"
    }

    NODE_TO_STAGE = {v: k for k, v in STAGE_TO_NODE.items()}

    NEXT_STAGE = {
        "bootstrap": "architecture",
        "architecture": "research",
        "research": "setup",
        "setup": "detail",
        "detail": "judge",
        "judge": "execute",
        "execute": "validate"
    }

    @staticmethod
    def get_next_node(current_stage: str) -> str:
        """
        Maps current stage to the next node name.
        """
        next_s = RoutingDecisionEngine.NEXT_STAGE.get(current_stage)
        if not next_s:
            return "done"
        return RoutingDecisionEngine.STAGE_TO_NODE.get(next_s, "done")

    @staticmethod
    def route(
        stage: str, 
        result: VerificationResult, 
        state: AgentState
    ) -> str:
        """
        Determines the next node path based on verification result and mode.
        Returns the node name (e.g. 'research', 'plan_bootstrap', 'error').
        """
        mode = state.get("verification_mode", VerificationMode.Strict)
        enabled = state.get("verification_enabled", True)

        if not enabled or mode == VerificationMode.Disabled:
            # Bypass checks entirely, proceed to next stage
            next_node = RoutingDecisionEngine.get_next_node(stage)
            logger.info("routing_bypass_checks", stage=stage, next_node=next_node)
            return next_node

        if result.passed and "node_exception" not in state:
            # Verification passed, move to next stage
            next_node = RoutingDecisionEngine.get_next_node(stage)
            logger.info("routing_verification_passed", stage=stage, next_node=next_node)
            return next_node

        # Verification failed or a node exception occurred
        
        # Check for non-retryable node exceptions
        if "node_exception" in state:
            exception_data = state["node_exception"]
            if isinstance(exception_data, dict) and exception_data.get("type") == "TemplateNotFoundError":
                logger.error("routing_escalate_static_config_error", stage=stage, error=exception_data.get("message"))
                return "error"

        checkpoint = result.checkpoint_data or CheckpointManager.get_checkpoint(stage, state)
        retry_count = checkpoint.retry_count if checkpoint else 0
        max_retries = checkpoint.max_retries if checkpoint else 3

        logger.warning(
            "routing_verification_failed",
            stage=stage,
            mode=mode,
            retry_count=retry_count,
            max_retries=max_retries,
            severity=result.severity
        )

        max_critical_retries = 2 if stage == "research" else 1
        if result.severity == 'Critical':
            if retry_count >= max_critical_retries:
                if mode == VerificationMode.Strict:
                    logger.error("routing_escalate_critical_strict", stage=stage, retry_count=retry_count)
                    return "error"
                else:
                    # Permissive mode: log warning and proceed (except judge)
                    if stage == "judge" and not state.get("plan_approved", False):
                        logger.warning("routing_prevent_permissive_execution", stage=stage)
                        return "error"
                    next_node = RoutingDecisionEngine.get_next_node(stage)
                    logger.warning("routing_continue_permissive_critical", stage=stage, next_node=next_node)
                    return next_node
            else:
                # First critical failure: retry the stage
                current_node = RoutingDecisionEngine.STAGE_TO_NODE.get(stage, "error")
                logger.info("routing_retry_critical", stage=stage, node=current_node, attempt=retry_count + 1)
                return current_node

        # Non-critical: standard max-retries exceeded check
        if retry_count >= max_retries:
            if mode == VerificationMode.Strict:
                logger.error("routing_escalate_max_retries_strict", stage=stage)
                return "error"
            else:
                # Permissive mode: proceed (except judge)
                if stage == "judge" and not state.get("plan_approved", False):
                    logger.warning("routing_prevent_permissive_execution", stage=stage)
                    return "error"
                next_node = RoutingDecisionEngine.get_next_node(stage)
                logger.warning("routing_continue_permissive", stage=stage, next_node=next_node)
                return next_node

        # Retry current stage
        current_node = RoutingDecisionEngine.STAGE_TO_NODE.get(stage, "error")
        logger.info("routing_retry_stage", stage=stage, node=current_node)
        return current_node
