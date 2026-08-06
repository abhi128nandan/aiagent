from typing import Dict, List, Any, Optional
from datetime import datetime
from agent.stage_checkpoint import StageCheckpoint

class CheckpointManager:
    STAGES = ["bootstrap", "architecture", "research", "setup", "detail", "judge", "execute"]

    @staticmethod
    def create_checkpoints() -> Dict[str, StageCheckpoint]:
        """
        Initializes a dictionary containing checkpoints for all seven pipeline stages
        with status 'Pending' and retry_count 0.
        """
        checkpoints = {}
        for stage in CheckpointManager.STAGES:
            checkpoints[stage] = StageCheckpoint(
                stage_name=stage,
                verification_status='Pending',
                retry_count=0,
                max_retries=3,
                failure_reasons=[],
                artifacts_validated=[],
                metrics={}
            )
        return checkpoints

    @staticmethod
    def get_checkpoint(stage_name: str, state: Dict[str, Any]) -> Optional[StageCheckpoint]:
        """
        Queries and returns a StageCheckpoint from state.
        """
        checkpoints = state.get('stage_checkpoints', {})
        return checkpoints.get(stage_name)

    @staticmethod
    def update_checkpoint(stage_name: str, status: str, state: Dict[str, Any]) -> None:
        """
        Updates status and verification timestamp of a checkpoint in the state.
        """
        checkpoints = state.get('stage_checkpoints', {})
        if stage_name in checkpoints:
            checkpoint = checkpoints[stage_name]
            checkpoint.verification_status = status
            checkpoint.verification_timestamp = datetime.utcnow().isoformat() + "Z"
            state['stage_checkpoints'] = checkpoints

    @staticmethod
    def reset_checkpoint(stage_name: str, state: Dict[str, Any]) -> None:
        """
        Resets retry count of a checkpoint to 0.
        """
        checkpoints = state.get('stage_checkpoints', {})
        if stage_name in checkpoints:
            checkpoints[stage_name].reset()
            state['stage_checkpoints'] = checkpoints

    @staticmethod
    def get_failed_stages(state: Dict[str, Any]) -> List[str]:
        """
        Identifies and returns all stages that currently have a status of 'Fail'.
        """
        checkpoints = state.get('stage_checkpoints', {})
        failed = []
        for stage, cp in checkpoints.items():
            # Support both Pydantic models and dictionaries
            status = cp.verification_status if hasattr(cp, 'verification_status') else cp.get('verification_status')
            if status == 'Fail':
                failed.append(stage)
        return failed

    @staticmethod
    def get_checkpoint_summary(state: Dict[str, Any]) -> str:
        """
        Generates a structured human-readable text summary of all checkpoints.
        """
        checkpoints = state.get('stage_checkpoints', {})
        if not checkpoints:
            return "No checkpoints initialized."
            
        summary_lines = ["### Stage Verification Checkpoints Summary:"]
        for stage in CheckpointManager.STAGES:
            cp = checkpoints.get(stage)
            if not cp:
                summary_lines.append(f"- **{stage}**: Not Initialized")
                continue
                
            status = cp.verification_status if hasattr(cp, 'verification_status') else cp.get('verification_status')
            retry = cp.retry_count if hasattr(cp, 'retry_count') else cp.get('retry_count', 0)
            max_r = cp.max_retries if hasattr(cp, 'max_retries') else cp.get('max_retries', 3)
            
            line = f"- **{stage}**: {status} (Retries: {retry}/{max_r})"
            
            reasons = cp.failure_reasons if hasattr(cp, 'failure_reasons') else cp.get('failure_reasons', [])
            if status == 'Fail' and reasons:
                line += f" - Reason: {reasons[-1]}"
            summary_lines.append(line)
            
        return "\n".join(summary_lines)
