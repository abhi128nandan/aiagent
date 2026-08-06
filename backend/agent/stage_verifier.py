import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from agent.stage_checkpoint import StageCheckpoint, VerificationResult
from agent.verification_rules import VerificationRuleEngine, Rule, RuleResult
from agent.state import AgentState

class StageVerifier:
    def __init__(self, rule_engine: Optional[VerificationRuleEngine] = None):
        self.rule_engine = rule_engine or VerificationRuleEngine()

    def verify(self, stage_name: str, state: AgentState) -> VerificationResult:
        """
        Executes all registered verification rules for a given stage against the agent state,
        updates the stage checkpoint, logs history, and returns the aggregated verification result.
        """
        start_time = time.time()
        rules = self.rule_engine.get_rules_for_stage(stage_name)
        
        # Initialize result structure
        passed = True
        max_severity = 'Info'
        errors: List[str] = []
        warnings: List[str] = []
        metrics: Dict[str, Any] = {}
        suggestions: List[str] = []
        artifacts_validated: List[str] = []

        # Run each rule
        for rule in rules:
            rule_result = rule.execute(state)
            artifacts_validated.append(rule.name)
            
            if not rule_result.passed:
                passed = False
                # Severity escalation logic
                severity_hierarchy = {'Info': 0, 'Warning': 1, 'Error': 2, 'Critical': 3}
                if severity_hierarchy[rule_result.severity] > severity_hierarchy[max_severity]:
                    max_severity = rule_result.severity
                
                errors.extend(rule_result.errors)
                suggestions.append(self._generate_suggestion_for_rule(rule.name, rule_result.errors))
            
            if rule_result.warnings:
                warnings.extend(rule_result.warnings)
            
            if rule_result.metrics:
                metrics.update(rule_result.metrics)

        # Get execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        metrics['execution_time_ms'] = execution_time_ms

        # Retrieve checkpoint
        stage_checkpoints = state.get('stage_checkpoints', {})
        checkpoint = stage_checkpoints.get(stage_name)
        
        # If checkpoints are not initialized, create a temporary checkpoint
        if not checkpoint:
            checkpoint = StageCheckpoint(
                stage_name=stage_name,
                verification_status='Pending',
                retry_count=0,
                max_retries=3
            )
            stage_checkpoints[stage_name] = checkpoint

        # Update checkpoint status and details
        checkpoint.verification_timestamp = datetime.utcnow().isoformat() + "Z"
        checkpoint.artifacts_validated = list(set(checkpoint.artifacts_validated + artifacts_validated))
        checkpoint.metrics.update(metrics)
        
        if passed:
            checkpoint.verification_status = 'Pass'
            checkpoint.reset()  # Reset retry count on success
        else:
            checkpoint.verification_status = 'Fail'
            checkpoint.increment_retry()
            checkpoint.failure_reasons.extend(errors)

        # Ensure state has checkpoints dictionary updated
        state['stage_checkpoints'] = stage_checkpoints

        # Append to verification history
        history = state.get('verification_history', [])
        history.append({
            'stage': stage_name,
            'timestamp': checkpoint.verification_timestamp,
            'passed': passed,
            'severity': max_severity,
            'errors': errors,
            'warnings': warnings,
            'retry_count': checkpoint.retry_count
        })
        state['verification_history'] = history

        # Generate output result
        result = VerificationResult(
            passed=passed,
            stage=stage_name,
            severity=max_severity,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
            suggestions=list(set(suggestions)),
            checkpoint_data=checkpoint,
            execution_time_ms=execution_time_ms
        )
        return result

    def _generate_suggestion_for_rule(self, rule_name: str, errors: List[str]) -> str:
        """
        Generates actionable developer suggestions based on specific rule failures.
        """
        suggestions_map = {
            'valid_json_plan': "Verify that the generated plan is formatted as a valid JSON string without syntax errors.",
            'required_fields_present': "Add missing fields to the bootstrap plan. Required: project, description, tech_stack, environment, scaffold_command.",
            'scaffold_command_valid': "Ensure the scaffold command does not expect interactive user inputs. Add flags like '-y' or '--yes'.",
            'all_artifacts_present': "Regenerate the architecture to ensure system_diagram, component_diagram, data_flow_diagram, deployment_diagram, and sequence_diagrams are present.",
            'valid_mermaid_syntax': "Fix Mermaid syntax errors (e.g., mismatched brackets, invalid arrows, unquoted special characters).",
            'adrs_created': "Ensure at least one Architecture Decision Record (ADR) file is created in ADR-001 format.",
            'research_context_populated': "Make sure research node retrieves background info on dependencies and scaffolding.",
            'research_findings_valid': "Provide structured research context containing compatible package versions.",
            'scaffold_executed': "Check if the workspace is writeable and the docker container runtime executes commands correctly.",
            'workspace_files_exist': "Check why the scaffold command did not generate files in the workspace directory.",
            'environment_ready_flag': "Verify that setup_environment node successfully sets environment_ready to True.",
            'steps_array_populated': "Plan detail must contain a non-empty 'steps' array outlining tasks.",
            'file_paths_match_workspace': "Ensure all step file paths are safe, clean, and stay within the workspace directory root.",
            'action_types_valid': "Only use allowed actions in step details: create, modify, run, write, replace, delete.",
            'judge_decision_present': "Wait for the judge node to evaluate the detail plan and populate the approval flag.",
            'max_judge_attempts': "The judge rejected the plan too many times. Simplify the architecture or requirements to align.",
            'action_executed': "Ensure the implementation step issues execute commands or file writes.",
            'exit_code_zero': "Debug why commands returned non-zero exit codes. Check compilation logs or dependency issues.",
            'no_command_injection': "Strict Security Alert: Avoid command injection structures like unquoted semicolons, nested subshells $(), or pipe execution."
        }
        return suggestions_map.get(rule_name, f"Fix rule '{rule_name}' validation failures: {'; '.join(errors[:2])}")
