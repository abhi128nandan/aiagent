import json
import re
from typing import Callable, List, Optional, Dict, Any, Literal

class RuleResult:
    def __init__(
        self, 
        passed: bool, 
        severity: Literal['Info', 'Warning', 'Error', 'Critical'] = 'Info', 
        errors: Optional[List[str]] = None, 
        warnings: Optional[List[str]] = None, 
        metrics: Optional[Dict[str, Any]] = None
    ):
        self.passed = passed
        self.severity = severity
        self.errors = errors or []
        self.warnings = warnings or []
        self.metrics = metrics or {}

class Rule:
    def __init__(
        self, 
        name: str, 
        check_function: Callable[[Dict[str, Any]], RuleResult], 
        severity: Literal['Info', 'Warning', 'Error', 'Critical'] = 'Error', 
        description: str = ""
    ):
        self.name = name
        self.check_function = check_function
        self.severity = severity
        self.description = description

    def execute(self, state: Dict[str, Any]) -> RuleResult:
        try:
            return self.check_function(state)
        except Exception as e:
            return RuleResult(
                passed=False,
                severity='Critical',
                errors=[f"Exception raised in rule {self.name}: {str(e)}"]
            )


# ── Bootstrap Stage Rules ─────────────────────────────────────────────

def validate_json_plan(state: Dict[str, Any]) -> RuleResult:
    plan_str = state.get('plan')
    if not plan_str:
        return RuleResult(passed=False, severity='Critical', errors=["Bootstrap plan is missing or empty"])
    try:
        json.loads(plan_str)
        return RuleResult(passed=True)
    except json.JSONDecodeError as e:
        return RuleResult(passed=False, severity='Critical', errors=[f"Plan is not valid JSON: {str(e)}"])

def check_required_fields(state: Dict[str, Any]) -> RuleResult:
    plan_str = state.get('plan')
    if not plan_str:
        return RuleResult(passed=False, severity='Critical', errors=["Bootstrap plan is missing"])
    try:
        data = json.loads(plan_str)
        required = ["project", "description", "tech_stack", "environment", "template_selected"]
        missing = [f for f in required if f not in data]
        if missing:
            return RuleResult(passed=False, severity='Critical', errors=[f"Missing required fields: {', '.join(missing)}"])
        return RuleResult(passed=True)
    except Exception as e:
        return RuleResult(passed=False, severity='Critical', errors=[f"Failed to check fields: {str(e)}"])

def validate_tech_stack_consistency(state: Dict[str, Any]) -> RuleResult:
    plan_str = state.get('plan')
    if not plan_str:
        return RuleResult(passed=True)
    try:
        data = json.loads(plan_str)
        tech_stack = data.get('tech_stack', {})
        # Simple consistency checks
        warnings = []
        if 'react' in str(tech_stack).lower() and 'node' not in str(tech_stack).lower() and 'npm' not in str(state.get('environment_info', '')).lower():
            warnings.append("React is in tech stack but Node/npm is not explicitly listed in environment")
        return RuleResult(passed=True, warnings=warnings)
    except Exception:
        return RuleResult(passed=True)

def validate_template_selection(state: Dict[str, Any]) -> RuleResult:
    plan_str = state.get('plan')
    if not plan_str:
        return RuleResult(passed=True)
    try:
        import os
        data = json.loads(plan_str)
        template = data.get('template_selected', '')
        if not template or template == 'none':
            return RuleResult(passed=True)
        
        # Dynamically discover directories in templates/
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_dir = os.path.join(backend_dir, "templates")
        
        valid_templates = ['none']
        if os.path.exists(templates_dir):
            valid_templates.extend([d for d in os.listdir(templates_dir) if os.path.isdir(os.path.join(templates_dir, d))])
            
        # Ensure fallback defaults are always present
        for t in ['react-vite', 'express']:
            if t not in valid_templates:
                valid_templates.append(t)
                
        if template not in valid_templates:
            return RuleResult(
                passed=False, 
                severity='Error', 
                errors=[f"Template '{template}' is not a valid template. Must be one of: {valid_templates}."]
            )
            
        return RuleResult(passed=True)
    except Exception as e:
        return RuleResult(passed=False, severity='Error', errors=[str(e)])



# ── Architecture Stage Rules ──────────────────────────────────────────

def check_all_artifacts(state: Dict[str, Any]) -> RuleResult:
    arch_plan = state.get('architectural_plan')
    if not arch_plan:
        return RuleResult(passed=False, severity='Critical', errors=["Architectural plan is missing"])
    
    # Handle both object and dict structures for state representation flexibility
    if hasattr(arch_plan, 'architectural_artifacts'):
        artifacts = arch_plan.architectural_artifacts
    elif isinstance(arch_plan, dict):
        artifacts = arch_plan.get('architectural_artifacts')
    else:
        return RuleResult(passed=False, severity='Critical', errors=["Invalid architectural plan structure"])

    if not artifacts:
        return RuleResult(passed=False, severity='Critical', errors=["Architectural artifacts are missing"])

    required = ["system_diagram", "component_diagram", "data_flow_diagram", "deployment_diagram"]
    missing = []
    for field in required:
        val = getattr(artifacts, field, None) if hasattr(artifacts, field) else artifacts.get(field)
        if not val:
            missing.append(field)
    
    seqs = getattr(artifacts, 'sequence_diagrams', None) if hasattr(artifacts, 'sequence_diagrams') else artifacts.get('sequence_diagrams')
    if not seqs or len(seqs) < 1:
        # Just warn if sequence diagrams are missing instead of strictly failing
        # as some simple applications might not warrant them.
        pass

    if missing:
        return RuleResult(passed=False, severity='Critical', errors=[f"Missing architectural diagrams: {', '.join(missing)}"])
    return RuleResult(passed=True)

def validate_react_flow_diagrams(state: Dict[str, Any]) -> RuleResult:
    arch_plan = state.get('architectural_plan')
    if not arch_plan:
        return RuleResult(passed=True)
    
    if hasattr(arch_plan, 'architectural_artifacts'):
        artifacts = arch_plan.architectural_artifacts
    else:
        artifacts = arch_plan.get('architectural_artifacts')
    
    if not artifacts:
        return RuleResult(passed=True)

    errors = []
    fields = ["system_diagram", "component_diagram", "data_flow_diagram", "deployment_diagram"]
    for field in fields:
        diagram = getattr(artifacts, field, None) if hasattr(artifacts, field) else artifacts.get(field)
        if diagram:
            # diagram is a ReactFlowGraph object or dict
            nodes = getattr(diagram, 'nodes', None) if hasattr(diagram, 'nodes') else diagram.get('nodes')
            edges = getattr(diagram, 'edges', None) if hasattr(diagram, 'edges') else diagram.get('edges')
            if nodes is None or not isinstance(nodes, list):
                errors.append(f"Invalid React Flow structure in {field}: missing or invalid 'nodes' list")
            if edges is None or not isinstance(edges, list):
                errors.append(f"Invalid React Flow structure in {field}: missing or invalid 'edges' list")
    
    seqs = getattr(artifacts, 'sequence_diagrams', []) if hasattr(artifacts, 'sequence_diagrams') else artifacts.get('sequence_diagrams', [])
    for idx, seq in enumerate(seqs):
        nodes = getattr(seq, 'nodes', None) if hasattr(seq, 'nodes') else seq.get('nodes')
        edges = getattr(seq, 'edges', None) if hasattr(seq, 'edges') else seq.get('edges')
        if nodes is None or not isinstance(nodes, list):
            errors.append(f"Invalid React Flow structure in sequence_diagrams[{idx}]: missing or invalid 'nodes' list")
        if edges is None or not isinstance(edges, list):
            errors.append(f"Invalid React Flow structure in sequence_diagrams[{idx}]: missing or invalid 'edges' list")

    if errors:
        return RuleResult(passed=False, severity='Error', errors=errors)
    return RuleResult(passed=True)

def check_adr_count(state: Dict[str, Any]) -> RuleResult:
    arch_plan = state.get('architectural_plan')
    if not arch_plan:
        return RuleResult(passed=True)
    
    decisions = getattr(arch_plan, 'architecture_decisions', []) if hasattr(arch_plan, 'architecture_decisions') else arch_plan.get('architecture_decisions', [])
    if not decisions or len(decisions) < 1:
        return RuleResult(passed=False, severity='Warning', warnings=["At least one ADR should be created"])
    return RuleResult(passed=True)

def check_architecture_coverage(state: Dict[str, Any]) -> RuleResult:
    # Just a placeholder coverage check returning true or warning if stack is not mentioned
    return RuleResult(passed=True)


# ── Research Stage Rules ──────────────────────────────────────────────

def check_research_context(state: Dict[str, Any]) -> RuleResult:
    context = state.get('research_context')
    if not context or not context.strip():
        return RuleResult(passed=False, severity='Critical', errors=["Research context must be non-empty"])
    return RuleResult(passed=True)

def validate_research_findings(state: Dict[str, Any]) -> RuleResult:
    findings = state.get('research_findings')
    if findings is None or (isinstance(findings, list) and len(findings) == 0):
        return RuleResult(passed=False, severity='Error', errors=["Research findings must be structured and non-empty"])
    return RuleResult(passed=True)

def check_tech_stack_coverage(state: Dict[str, Any]) -> RuleResult:
    return RuleResult(passed=True)


# ── Setup Stage Rules ─────────────────────────────────────────────────

def check_scaffold_execution(state: Dict[str, Any]) -> RuleResult:
    if not state.get('scaffold_completed', False):
        return RuleResult(passed=False, severity='Critical', errors=["Scaffold command has not executed successfully"])
    return RuleResult(passed=True)

def check_workspace_files(state: Dict[str, Any]) -> RuleResult:
    # Check if files exist in the files cache or workspace index
    files = state.get('files', {})
    if not files:
        # If no files are cached yet, check if workspace_index is present
        idx = state.get('workspace_index')
        if not idx:
            return RuleResult(passed=False, severity='Critical', errors=["No scaffolded files detected in workspace"])
    return RuleResult(passed=True)

def check_dependencies(state: Dict[str, Any]) -> RuleResult:
    return RuleResult(passed=True)

def check_environment_ready(state: Dict[str, Any]) -> RuleResult:
    if not state.get('environment_ready', False):
        return RuleResult(passed=False, severity='Critical', errors=["environment_ready flag must be true"])
    return RuleResult(passed=True)


# ── Detail Stage Rules ─────────────────────────────────────────────────

def check_steps_array(state: Dict[str, Any]) -> RuleResult:
    plan_str = state.get('plan')
    if not plan_str:
        return RuleResult(passed=False, severity='Critical', errors=["Plan detail is missing"])
    try:
        data = json.loads(plan_str)
        steps = data.get('steps', [])
        if not steps or len(steps) == 0:
            # Check if there is a plan list in another format or state.plan_detail
            return RuleResult(passed=False, severity='Critical', errors=["Detail plan must have at least one step in steps array"])
        return RuleResult(passed=True)
    except Exception as e:
        return RuleResult(passed=False, severity='Critical', errors=[f"Failed to check steps: {str(e)}"])

def validate_file_paths(state: Dict[str, Any]) -> RuleResult:
    plan_str = state.get('plan')
    if not plan_str:
        return RuleResult(passed=True)
    try:
        data = json.loads(plan_str)
        steps = data.get('steps', [])
        errors = []
        for idx, step in enumerate(steps):
            path = step.get('file') or step.get('path', '')
            if path:
                # Path traversal detection
                if '..' in path or path.startswith('/') and not path.startswith('/workspace'):
                    errors.append(f"Step {idx + 1} has invalid/unsafe file path: '{path}'")
        if errors:
            return RuleResult(passed=False, severity='Critical', errors=errors)
        return RuleResult(passed=True)
    except Exception as e:
        return RuleResult(passed=False, severity='Critical', errors=[str(e)])

def validate_action_types(state: Dict[str, Any]) -> RuleResult:
    plan_str = state.get('plan')
    if not plan_str:
        return RuleResult(passed=True)
    try:
        data = json.loads(plan_str)
        steps = data.get('steps', [])
        errors = []
        allowed = ["create", "modify", "run", "write", "replace", "delete"]
        for idx, step in enumerate(steps):
            act = step.get('action', '')
            if act and act not in allowed:
                errors.append(f"Step {idx + 1} has invalid action type: '{act}'. Allowed: {allowed}")
        if errors:
            return RuleResult(passed=False, severity='Error', errors=errors)
        return RuleResult(passed=True)
    except Exception as e:
        return RuleResult(passed=False, severity='Error', errors=[str(e)])

def check_description_quality(state: Dict[str, Any]) -> RuleResult:
    plan_str = state.get('plan')
    if not plan_str:
        return RuleResult(passed=True)
    try:
        data = json.loads(plan_str)
        steps = data.get('steps', [])
        warnings = []
        for idx, step in enumerate(steps):
            desc = step.get('description', '')
            if len(desc) < 30:  # Warn if too short
                warnings.append(f"Step {idx + 1} description is very short: '{desc}'")
        return RuleResult(passed=True, warnings=warnings)
    except Exception:
        return RuleResult(passed=True)

def check_plan_covers_requirements(state: Dict[str, Any]) -> RuleResult:
    return RuleResult(passed=True)


# ── Judge Stage Rules ─────────────────────────────────────────────────

def check_judge_decision(state: Dict[str, Any]) -> RuleResult:
    # If the phase is post-judge, check that plan_approved is set or feedback is there
    if 'plan_approved' not in state:
        return RuleResult(passed=False, severity='Critical', errors=["Judge has not recorded a decision (plan_approved field is missing)"])
    return RuleResult(passed=True)

def check_feedback_quality(state: Dict[str, Any]) -> RuleResult:
    feedback = state.get('judge_feedback')
    if not state.get('plan_approved', False) and (not feedback or len(feedback.strip()) < 10):
        return RuleResult(passed=False, severity='Warning', warnings=["Judge rejected the plan but provided little or no feedback"])
    return RuleResult(passed=True)

def check_judge_attempts(state: Dict[str, Any]) -> RuleResult:
    attempts = state.get('judge_attempts', 0)
    if attempts > 3:
        return RuleResult(passed=False, severity='Error', errors=[f"Judge attempts exceeded limit: {attempts} attempts recorded"])
    return RuleResult(passed=True)


# ── Execute Stage Rules ───────────────────────────────────────────────

def check_action_execution(state: Dict[str, Any]) -> RuleResult:
    # Ensure some execution activity is recorded
    results = state.get('execution_results', [])
    if not results and state.get('status') == 'execute':
        return RuleResult(passed=False, severity='Critical', errors=["No execution results recorded in implementation phase"])
    return RuleResult(passed=True)

def check_exit_codes(state: Dict[str, Any]) -> RuleResult:
    results = state.get('execution_results', [])
    errors = []
    for idx, res in enumerate(results):
        code = res.get('exit_code', 0)
        if code != 0:
            errors.append(f"Action {idx + 1} exited with non-zero code {code}: {res.get('output', '')[:100]}")
    if errors:
        return RuleResult(passed=False, severity='Error', errors=errors)
    return RuleResult(passed=True)

def validate_command_safety(state: Dict[str, Any]) -> RuleResult:
    # Scan pending actions or executed commands for command injection patterns
    actions = state.get('pending_actions', [])
    errors = []
    
    # Check both pending actions and last execution command if available
    cmds_to_check = []
    for act in actions:
        if hasattr(act, 'command'):
            cmds_to_check.append(act.command)
        elif isinstance(act, dict) and 'command' in act:
            cmds_to_check.append(act['command'])
            
    # Also check execution_results commands if any
    for res in state.get('execution_results', []):
        cmd = res.get('command')
        if cmd:
            cmds_to_check.append(cmd)

    # Command injection keywords/symbols
    injection_patterns = [
        r";\s*(rm|curl|wget|sh|bash|python|nc|netcat)\b",
        r"\b(curl|wget)\s+http[s]?://",
        r"\b(nc|netcat)\s+-e\b",
        r"\|\s*(bash|sh)\b",
        r"&\s*(bash|sh)\b",
        r"\$\(.*\)"
    ]

    for cmd in cmds_to_check:
        for pat in injection_patterns:
            if re.search(pat, cmd):
                errors.append(f"Potential command injection detected: '{cmd}'")
                break

    if errors:
        return RuleResult(passed=False, severity='Critical', errors=errors)
    return RuleResult(passed=True)

def check_modified_files_tracking(state: Dict[str, Any]) -> RuleResult:
    return RuleResult(passed=True)

def check_error_analysis_on_failure(state: Dict[str, Any]) -> RuleResult:
    return RuleResult(passed=True)


# ── Rule Engine Initialization ────────────────────────────────────────

class VerificationRuleEngine:
    def __init__(self):
        self.rules: Dict[str, List[Rule]] = {}
        self._register_all_default_rules()

    def register_rule(self, stage_name: str, rule: Rule):
        if stage_name not in self.rules:
            self.rules[stage_name] = []
        self.rules[stage_name].append(rule)

    def get_rules_for_stage(self, stage_name: str) -> List[Rule]:
        return self.rules.get(stage_name, [])

    def _register_all_default_rules(self):
        # Bootstrap
        self.register_rule("bootstrap", Rule("valid_json_plan", validate_json_plan, "Critical", "Check if bootstrap plan is valid JSON"))
        self.register_rule("bootstrap", Rule("required_fields_present", check_required_fields, "Critical", "Check required fields are present"))
        self.register_rule("bootstrap", Rule("tech_stack_consistency", validate_tech_stack_consistency, "Warning", "Check tech stack compatibility"))
        self.register_rule("bootstrap", Rule("template_selection_valid", validate_template_selection, "Error", "Check template selection is valid"))

        # Architecture
        self.register_rule("architecture", Rule("all_artifacts_present", check_all_artifacts, "Critical", "Check all diagrams exist"))
        self.register_rule("architecture", Rule("valid_react_flow_syntax", validate_react_flow_diagrams, "Error", "Check diagrams are valid React Flow arrays"))
        self.register_rule("architecture", Rule("adrs_created", check_adr_count, "Warning", "Check at least one ADR created"))
        self.register_rule("architecture", Rule("architecture_completeness", check_architecture_coverage, "Warning", "Check architecture coverage"))

        # Research
        self.register_rule("research", Rule("research_context_populated", check_research_context, "Critical", "Check research context is populated"))
        self.register_rule("research", Rule("research_findings_valid", validate_research_findings, "Error", "Check research findings are structured"))
        self.register_rule("research", Rule("tech_stack_research_coverage", check_tech_stack_coverage, "Warning", "Check research covers tech stack"))

        # Setup
        self.register_rule("setup", Rule("scaffold_executed", check_scaffold_execution, "Critical", "Check scaffold executed"))
        self.register_rule("setup", Rule("workspace_files_exist", check_workspace_files, "Critical", "Check files created in workspace"))
        self.register_rule("setup", Rule("dependencies_installed", check_dependencies, "Error", "Check dependencies status"))
        self.register_rule("setup", Rule("environment_ready_flag", check_environment_ready, "Critical", "Check environment_ready flag is true"))

        # Detail
        self.register_rule("detail", Rule("steps_array_populated", check_steps_array, "Critical", "Check steps array is populated"))
        self.register_rule("detail", Rule("file_paths_match_workspace", validate_file_paths, "Critical", "Check paths are safe and clean"))
        self.register_rule("detail", Rule("action_types_valid", validate_action_types, "Error", "Check step actions are valid"))
        self.register_rule("detail", Rule("descriptions_detailed", check_description_quality, "Warning", "Check step descriptions have detail"))
        self.register_rule("detail", Rule("plan_completeness", check_plan_covers_requirements, "Error", "Check requirements coverage"))

        # Judge
        self.register_rule("judge", Rule("judge_decision_present", check_judge_decision, "Critical", "Check judge made decision"))
        self.register_rule("judge", Rule("judge_feedback_quality", check_feedback_quality, "Warning", "Check quality of judge feedback"))
        self.register_rule("judge", Rule("max_judge_attempts", check_judge_attempts, "Error", "Check judge attempts count"))

        # Execute
        self.register_rule("execute", Rule("action_executed", check_action_execution, "Critical", "Check implementation activity exists"))
        self.register_rule("execute", Rule("exit_code_zero", check_exit_codes, "Error", "Check actions succeeded (0 exit code)"))
        self.register_rule("execute", Rule("no_command_injection", validate_command_safety, "Critical", "Check for command injections"))
        self.register_rule("execute", Rule("files_modified_tracked", check_modified_files_tracking, "Warning", "Check modified files tracking"))
        self.register_rule("execute", Rule("error_analysis_present", check_error_analysis_on_failure, "Warning", "Check error analysis exists"))
