from typing import Literal, Annotated, Dict, Any, Optional, NotRequired, List, Union
from typing_extensions import TypedDict, Literal, Annotated, Dict, Any, Optional, NotRequired, List, Union
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from .schema import ActionType, ObservationType
from models.llm_profile import LLMProfile
from agent.architectural_artifacts import ArchitecturalPlan
from agent.stage_checkpoint import StageCheckpoint, VerificationMode


class AgentState(TypedDict, total=False):
    # ── Core State ────────────────────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]   # full chat history
    status: Literal['plan', 'plan_refine', 'architecture', 'research', 'setup_env', 'judge', 'judge_structural', 'supervisor', 'implement', 'backend_subagent', 'frontend_subagent', 'contract_check', 'contract_structural', 'merge', 'execute', 'execute_structural', 'validate', 'validate_structural', 'done', 'error']
    session_id: str
    trace_id: str
    stage_id: str
    parent_span_id: str
    llm_profile: Optional[LLMProfile]
    chat_mode: Literal['build', 'discuss']  # current chat mode
    
    # ── Planning & Execution ──────────────────────────────────────────
    plan: str                               # project plan JSON
    tech_stack: Dict[str, str]              # preserved tech_stack from bootstrap
    current_task_index: int                 # index of current task being executed
    plan_generated_at: str                  # ISO timestamp of plan creation
    pending_actions: List[ActionType]       # actions queued for execution
    execution_results: List[Dict[str, Any]] # results from action execution
    modified_files: List[str]               # list of files modified in session
    
    # ── Two-Phase Planning ────────────────────────────────────────────
    planning_phase: Literal['bootstrap', 'refine']  # current planning phase
    scaffold_completed: bool                # whether scaffold command has run successfully
    
    # ── File Management ───────────────────────────────────────────────
    files: Dict[str, str]                   # path -> content cache
    locked_files: List[str]                 # files that cannot be modified
    
    # ── Docker Runtime ────────────────────────────────────────────────
    container_id: str                       # Docker container ID
    workspace_path: str                     # path to workspace directory
    last_obs: Optional[ObservationType]     # last Docker observation
    _action: Optional[ActionType]           # parsed XML action passed to execute
    
    # ── Retry & Error Handling ────────────────────────────────────────
    retries: int                            # global retry counter
    retry_count: int                        # retry count for current task
    max_retries: int                        # maximum retries allowed (default: 5)
    node_exception: Optional[Dict[str, str]]        # exception dict with type and message
    has_execution_errors: bool              # flag indicating errors in last execution
    has_validation_errors: bool             # flag indicating validation errors
    validation_errors: List[str]            # list of validation error messages
    validation_warnings: List[str]          # list of validation warnings
    
    # ── Subagent Supervisor ───────────────────────────────────────────
    api_contract: str                       # generated API contract between backend and frontend
    backend_retries: int                    # retry counter for backend subagent
    frontend_retries: int                   # retry counter for frontend subagent
    contract_mismatch: bool                 # flag indicating if the contract check failed

    # ── Pipeline Refactor & Two-Tier Gates ────────────────────────────
    subagents_needed: List[Literal["backend", "frontend"]]  # required subagents for execution iteration
    judge_structural_ok: bool               # flag indicating judge structural validation passed
    contract_structural_ok: bool            # flag indicating contract structural diff passed
    execute_structural_ok: bool             # flag indicating execution pre-conditions passed
    validate_structural_ok: bool            # flag indicating test artifacts exist and are parseable
    execute_retry_count: int                # retry count for execution semantic checks (default: 0)
    validate_retry_count: int               # retry count for validation semantic checks (default: 0)

    # ── Phase 1: Token & Context Management ──────────────────────────
    token_count: int                        # current total token usage
    context_budget: Dict[str, int]          # token budget allocation
    context_overflow_count: int             # number of times context was pruned
    total_tokens_processed: int             # Cumulative sum of all tokens processed across all LLM calls in the session. Tracks total token consumption for monitoring and optimization.
    total_pruning_events: int               # Counter incremented each time message pruning occurs to fit within token budget. Indicates frequency of context management interventions.
    total_overflow_events: int              # Counter incremented when overflow handling strategies (aggressive pruning/truncation) are triggered. Indicates severe context pressure situations.
    max_token_count_reached: int            # Peak token count reached at any point during the session. Used to track maximum context window usage for capacity planning.

    # ── Phase 2: Error Intelligence ──────────────────────────────────
    error_history: List[Dict[str, Any]]     # structured error analysis history
    last_error_analysis: Optional[Dict[str, Any]]  # last parsed error analysis
    internal_validation_errors: List[str]   # errors from static validation

    # ── Phase 3: Workspace Awareness ─────────────────────────────────
    workspace_summary: str                  # compact workspace context for LLM
    workspace_index: Optional[Dict[str, Any]]  # full workspace index from WorkspaceIndexer
    rag_context: Optional[Any]              # RAG retriever for SRS documents

    # ── Phase 4: Environment Setup ───────────────────────────────────
    environment_info: str                   # detected runtime/tools info for LLM
    environment_ready: bool                 # flag indicating environment is set up
    setup_completed_at: str                 # ISO timestamp of environment setup

    # ── Phase 5: Web Research ────────────────────────────────────────
    research_context: str                   # synthesized web research
    research_findings: List[Dict[str, Any]] # structured research results
    needs_research: bool                    # flag indicating research is needed

    # ── Phase 6: Plan Judging ────────────────────────────────────────
    judge_feedback: str                     # feedback or critique from the judge
    plan_approved: bool                     # whether the judge approved the plan
    judge_attempts: int                     # counter for plan revision loops
    plan_error: str                         # error message if plan parsing failed
    
    # ── Validation ────────────────────────────────────────────────────
    validation_results: List[Dict[str, Any]]  # results from validation checks
    validation_passed: bool                 # flag indicating validation passed
    app_port: int                           # port where app is running
    health_endpoint: str                    # health check endpoint path
    
    # ── Memory & Learning ─────────────────────────────────────────────
    memory: Optional[Any]                   # MemoryManager instance
    last_prompt: str                        # last prompt sent to LLM (for debugging)
    implementation_explanation: str         # explanation from implementation node

    # ── Architectural Planning ────────────────────────────────────────
    architectural_plan: ArchitecturalPlan
    architecture_phase: Literal['NotStarted', 'InProgress', 'Complete', 'Rejected']

    # ── Staged Verification ───────────────────────────────────────────
    stage_checkpoints: Dict[str, StageCheckpoint]
    current_checkpoint: str
    verification_history: List[Dict[str, Any]]
    verification_enabled: bool
    verification_mode: VerificationMode

    # ── Enhanced Error Tracking ───────────────────────────────────────
    stage_error_counts: Dict[str, int]
    critical_failure_threshold: int


