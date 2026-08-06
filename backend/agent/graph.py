import os
from contextlib import AsyncExitStack

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .nodes import plan_bootstrap_node, setup_environment_node, implement_node, execute_node, validate_node, plan_refine_node
from .research_node import research_node
from .subagents import supervisor_node, backend_subagent_node, frontend_subagent_node, contract_check_node, merge_workspace_node
from .judge_node import judge_node
from .state import AgentState
from core.config import get_settings
from core.logger import get_logger
from agent.stage_verifier import StageVerifier
from agent.routing_decision_engine import RoutingDecisionEngine
from agent.architecture_planner_node import architecture_plan_node

logger = get_logger(__name__)
settings = get_settings()

# ── Module-level singleton ──────────────────────────────────────────────
_compiled_graph = None
_checkpointer_stack = AsyncExitStack()

# ── Error categories that signal a wrong approach, not a typo ───────────
# Must match agent.error_analyzer.ErrorCategory values.
_REPLAN_ERROR_CATEGORIES = frozenset({
    'dependency', 'build',
})


def route_after_execute(state: AgentState) -> str:
    """
    Intelligent retry routing (Issue #5).

    Instead of a flat retry counter, this checks:
      1. Was execution successful? → route back to implement for next action
      2. Is the error fatal / architectural? → return to plan node
      3. Is it an environment issue? → try again (setup node handled env)
      4. Have we exhausted implementation retries (>= 3)? → return to plan
      5. Have we exhausted ALL retries (>= 5)? → give up
      6. Otherwise → retry implementation with error context
    """
    obs = state.get('last_obs')
    retries = state.get('retries', 0)

    # If critical failure or status is error, immediately halt
    if state.get("status") == "error":
        return "max_retry"

    # ── Success → back to implement for next action / finish ───────────
    if obs and getattr(obs, 'exit_code', 1) == 0:
        return 'success'

    # ── Hard stop ──────────────────────────────────────────────────────
    if retries >= 5:
        return 'max_retry'


    # ── Intelligent error-based routing ────────────────────────────────
    # last_error_analysis is a formatted STRING (for the LLM prompt);
    # structured category/severity live in error_history entries.
    error_history = state.get('error_history') or []
    last_error = error_history[-1] if error_history else {}

    if isinstance(last_error, dict):
        category = last_error.get('category', '')
        severity = last_error.get('severity', '')

        # Fatal severity or approach-level categories after a retry → re-plan
        if severity == 'fatal' or (category in _REPLAN_ERROR_CATEGORIES and retries >= 2):
            logger.warning(
                "fatal_error_return_to_plan",
                session_id=state.get('session_id', ''),
                category=category,
                severity=severity,
            )
            return 'return_to_plan'

    # Check for repeated identical errors (same category 3+ times)
    if len(error_history) >= 3:
        recent_categories = [
            e.get('category', '') for e in error_history[-3:]
        ]
        if len(set(recent_categories)) == 1 and recent_categories[0]:
            # Same error 3 times in a row → try a different approach
            logger.warning(
                "repeated_error_return_to_plan",
                session_id=state.get('session_id', ''),
                category=recent_categories[0],
                streak=3,
            )
            return 'return_to_plan'

    # After 3 retries of the same task, try replanning
    if retries >= 3:
        logger.info(
            "retry_threshold_return_to_plan",
            session_id=state.get('session_id', ''),
            retries=retries,
        )
        return 'return_to_plan'

    # Default: retry implementation with error context
    return 'error'


def route_after_validate(state: AgentState) -> str:
    obs = state.get('last_obs')
    return 'pass' if obs and getattr(obs, 'app_started', False) else 'fail'


def route_after_implement(state: AgentState) -> str:
    # If the retry limit has been exceeded, abort
    if state.get('retries', 0) >= 5:
        return 'max_retry'

    # If the implement node emitted <finish>, go to validate
    status = state.get('status')
    if status == 'validate':
        return 'validate'
    if status == 'done':
        return 'done'
    # Multi-action batch completed, need more LLM turns
    if status == 'implement':
        return 'implement_loop'
    return 'execute'


def route_after_judge(state: AgentState) -> str:
    """
    Route after judge evaluation.
    
    Key change for two-phase planning:
    - On rejection, route to plan_detail (NOT plan_bootstrap)
      because the scaffold is already done — we only need to
      re-generate the file-level implementation steps.
    """
    approved = state.get('plan_approved', False)
    attempts = state.get('judge_attempts', 0)
    if approved:
        return 'supervisor'
    if attempts >= 3:
        logger.warning("judge_max_attempts_exceeded_proceeding_to_architecture_replanning", session_id=state.get('session_id', ''))
        return 'architecture_plan'
    # On rejection, route back to plan_refine (scaffold already done)
    return 'plan_refine'



async def _create_checkpointer():
    """
    Try to create a PostgreSQL checkpointer for durable state persistence.
    Falls back to in-memory if the database is unavailable.
    """
    if os.environ.get("USE_MEMORY_CHECKPOINTER", "false").lower() in ("true", "1", "yes"):
        logger.info("checkpointer_init", backend="memory", reason="USE_MEMORY_CHECKPOINTER set")
        return MemorySaver()

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        # Create isolated exit stack for Postgres
        pg_stack = AsyncExitStack()
        checkpointer = await pg_stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(settings.database_url)
        )
        await checkpointer.setup()  # creates tables if they don't exist
        
        # Transfer context to global stack only after successful setup
        _checkpointer_stack.push_async_callback(pg_stack.aclose)
        logger.info("checkpointer_init", backend="postgres")
        return checkpointer
    except Exception as e:
        logger.warning(
            "checkpointer_fallback",
            reason=str(e),
            backend="memory",
        )
        return MemorySaver()
async def close_checkpointer():
    """Close any long-lived checkpointer resources."""
    global _checkpointer_stack
    await _checkpointer_stack.aclose()
    _checkpointer_stack = AsyncExitStack()


# ── Wrapped Nodes with Staged Verification ───────────────────────────


async def plan_bootstrap_node_wrapped(state: AgentState) -> AgentState:
    new_state = await plan_bootstrap_node(state)
    verifier = StageVerifier()
    res = verifier.verify("bootstrap", new_state)
    next_node = RoutingDecisionEngine.route("bootstrap", res, new_state)
    node_to_status = {
        "plan_bootstrap": "plan",
        "architecture_plan": "architecture",
        "error": "error"
    }
    new_state["status"] = node_to_status.get(next_node, new_state.get("status", "architecture"))
    return new_state

async def architecture_plan_node_wrapped(state: AgentState) -> AgentState:
    new_state = await architecture_plan_node(state)
    verifier = StageVerifier()
    res = verifier.verify("architecture", new_state)
    next_node = RoutingDecisionEngine.route("architecture", res, new_state)
    node_to_status = {
        "architecture_plan": "architecture",
        "research": "research",
        "error": "error"
    }
    new_state["status"] = node_to_status.get(next_node, new_state.get("status", "research"))
    return new_state

async def research_node_wrapped(state: AgentState) -> AgentState:
    new_state = await research_node(state)
    verifier = StageVerifier()
    res = verifier.verify("research", new_state)
    next_node = RoutingDecisionEngine.route("research", res, new_state)
    node_to_status = {
        "research": "research",
        "setup_environment": "setup_env",
        "error": "error"
    }
    new_state["status"] = node_to_status.get(next_node, new_state.get("status", "setup_env"))
    return new_state

async def setup_environment_node_wrapped(state: AgentState) -> AgentState:
    new_state = await setup_environment_node(state)
    verifier = StageVerifier()
    res = verifier.verify("setup", new_state)
    next_node = RoutingDecisionEngine.route("setup", res, new_state)
    node_to_status = {
        "setup_environment": "setup_env",
        "plan_detail": "plan_detail",
        "error": "error"
    }
    new_state["status"] = node_to_status.get(next_node, new_state.get("status", "plan_detail"))
    return new_state

async def plan_refine_node_wrapped(state: AgentState) -> AgentState:
    new_state = await plan_refine_node(state)
    verifier = StageVerifier()
    res = verifier.verify("detail", new_state)
    next_node = RoutingDecisionEngine.route("detail", res, new_state)
    node_to_status = {
        "plan_refine": "plan_refine",
        "judge": "judge",
        "error": "error"
    }
    new_state["status"] = node_to_status.get(next_node, new_state.get("status", "judge"))
    return new_state

async def judge_node_wrapped(state: AgentState) -> AgentState:
    new_state = await judge_node(state)
    verifier = StageVerifier()
    res = verifier.verify("judge", new_state)
    next_node = RoutingDecisionEngine.route("judge", res, new_state)
    node_to_status = {
        "judge": "judge",
        "execute": "execute",
        "error": "error"
    }
    if not res.passed:
        new_state["status"] = node_to_status.get(next_node, new_state.get("status", "execute"))
    return new_state

async def execute_node_wrapped(state: AgentState) -> AgentState:
    new_state = await execute_node(state)
    verifier = StageVerifier()
    res = verifier.verify("execute", new_state)
    if not res.passed:
        new_state["has_execution_errors"] = True
        if res.severity == "Critical":
            new_state["status"] = "error"
    return new_state


# ── Conditional Routing Helpers ──────────────────────────────────────

def route_after_bootstrap(state: AgentState) -> str:
    status = state.get("status")
    if status == "plan":
        return "plan_bootstrap"
    if status == "error":
        return "error"
    return "architecture_plan"

def route_after_architecture(state: AgentState) -> str:
    status = state.get("status")
    if status == "architecture":
        return "architecture_plan"
    if status == "error":
        return "error"
    return "research"

def route_after_research(state: AgentState) -> str:
    status = state.get("status")
    if status == "research":
        return "research"
    if status == "error":
        return "error"
    return "setup_environment"

def route_after_setup(state: AgentState) -> str:
    status = state.get("status")
    if status == "setup_env":
        return "setup_environment"
    if status == "error":
        return "error"
    return "plan_refine"

def route_after_refine(state: AgentState) -> str:
    status = state.get("status")
    if status == "plan_refine":
        return "plan_refine"
    if status == "error":
        return "error"
    return "judge"

def route_subagents(state: AgentState) -> str:
    # A generic router that just follows the 'status' field set by the nodes
    return state.get("status", "error")



async def build_graph(checkpointer=None):
    """
    Build and compile the LangGraph state machine.
    
    Two-Phase Planning Flow:
      plan_bootstrap → research → setup_environment (runs scaffold)
                    → plan_detail (re-indexes workspace, generates file steps)
                    → judge → implement → execute → validate → END
    """
    if checkpointer is None:
        checkpointer = await _create_checkpointer()

    g = StateGraph(AgentState)

    g.add_node('plan_bootstrap', plan_bootstrap_node_wrapped)
    g.add_node('architecture_plan', architecture_plan_node_wrapped)
    g.add_node('research', research_node_wrapped)
    g.add_node('setup_environment', setup_environment_node_wrapped)
    g.add_node('plan_refine', plan_refine_node_wrapped)
    g.add_node('judge', judge_node_wrapped)
    
    # Subagent Supervisor Nodes
    g.add_node('supervisor', supervisor_node)
    g.add_node('backend_subagent', backend_subagent_node)
    g.add_node('frontend_subagent', frontend_subagent_node)
    g.add_node('contract_check', contract_check_node)
    g.add_node('merge', merge_workspace_node)
    
    g.add_node('execute', execute_node_wrapped)
    g.add_node('validate', validate_node)

    def route_start(state: AgentState) -> str:
        status = state.get("status", "plan")
        mapping = {
            "plan": "plan_bootstrap",
            "architecture": "architecture_plan",
            "research": "research",
            "setup_env": "setup_environment",
            "plan_refine": "plan_refine",
            "plan_detail": "plan_refine",  # Add mapping for plan_detail status
            "judge": "judge",
            "supervisor": "supervisor",
            "backend_subagent": "backend_subagent",
            "frontend_subagent": "frontend_subagent",
            "contract_check": "contract_check",
            "merge": "merge",
            "execute": "execute",
            "validate": "validate",
            "error": END  # Stop execution on unrecoverable error instead of infinite looping
        }
        return mapping.get(status, "plan_bootstrap")

    # Flow: plan_bootstrap → research → setup_environment → plan_detail → judge
    g.set_conditional_entry_point(route_start, {
        "plan_bootstrap": "plan_bootstrap",
        "architecture_plan": "architecture_plan",
        "research": "research",
        "setup_environment": "setup_environment",
        "plan_refine": "plan_refine",
        "judge": "judge",
        "supervisor": "supervisor",
        "backend_subagent": "backend_subagent",
        "frontend_subagent": "frontend_subagent",
        "contract_check": "contract_check",
        "merge": "merge",
        "execute": "execute",
        "validate": "validate",
        END: END
    })
    
    g.add_conditional_edges('plan_bootstrap', route_after_bootstrap, {
        'plan_bootstrap': 'plan_bootstrap',
        'architecture_plan': 'architecture_plan',
        'error': END
    })
    g.add_conditional_edges('architecture_plan', route_after_architecture, {
        'architecture_plan': 'architecture_plan',
        'research': 'research',
        'error': END
    })
    g.add_conditional_edges('research', route_after_research, {
        'research': 'research',
        'setup_environment': 'setup_environment',
        'error': END
    })
    g.add_conditional_edges('setup_environment', route_after_setup, {
        'setup_environment': 'setup_environment',
        'plan_refine': 'plan_refine',
        'error': END
    })
    g.add_conditional_edges('plan_refine', route_after_refine, {
        'plan_refine': 'plan_refine',
        'judge': 'judge',
        'error': END
    })

    # Judge routes:
    #   - 'supervisor': plan approved, start coding (new subagent flow)
    #   - 'plan_refine': rejected, re-generate refine steps (scaffold already done)
    #   - 'architecture_plan': max judge attempts exceeded, trigger architectural re-planning
    g.add_conditional_edges('judge', route_after_judge, {
        'plan_refine': 'plan_refine',
        'architecture_plan': 'architecture_plan',
        'supervisor': 'supervisor'
    })

    # Subagent Supervisor Routing
    g.add_conditional_edges('supervisor', route_subagents, {
        'backend_subagent': 'backend_subagent'
    })
    g.add_conditional_edges('backend_subagent', route_subagents, {
        'backend_subagent': 'backend_subagent', # Retry loop
        'frontend_subagent': 'frontend_subagent'
    })
    g.add_conditional_edges('frontend_subagent', route_subagents, {
        'contract_check': 'contract_check'
    })
    g.add_conditional_edges('contract_check', route_subagents, {
        'merge': 'merge',
        'frontend_subagent': 'frontend_subagent' # Retry loop on mismatch
    })
    g.add_conditional_edges('merge', route_subagents, {
        'execute': 'execute'
    })

    g.add_conditional_edges('execute', route_after_execute, {
        'error': 'supervisor',          # fixable error → retry implementation
        'success': 'supervisor',        # go back to write more code until <finish>
        'max_retry': END,              # exhausted all retries → give up
        'return_to_plan': 'plan_refine',  # fatal/repeated error → re-plan refine steps
    })

    g.add_conditional_edges('validate', route_after_validate, {
        'pass': END,
        'fail': 'supervisor',
    })

    # Compile the graph with checkpointer
    # Note: recursion_limit is set at invocation time, not compile time
    return g.compile(checkpointer=checkpointer)


async def get_graph():
    """Return a cached compiled graph (singleton per process)."""
    global _compiled_graph
    if _compiled_graph is None:
        try:
            _compiled_graph = await build_graph()
        except Exception as e:
            logger.warning("get_graph_failed_rebuilding_with_memory", error=str(e))
            _compiled_graph = await build_graph(checkpointer=MemorySaver())
    return _compiled_graph
