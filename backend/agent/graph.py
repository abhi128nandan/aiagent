import os
from contextlib import AsyncExitStack
from typing import Any, cast

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .nodes import plan_bootstrap_node, setup_environment_node, implement_node, execute_node, validate_node, plan_refine_node, execute_structural_check, validate_structural_check
from .research_node import research_node
from .subagents import supervisor_node, backend_subagent_node, frontend_subagent_node, contract_check_node, merge_workspace_node, contract_structural_check
from .judge_node import judge_node, judge_structural_check
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


def _is_abap_project(state: AgentState) -> bool:
    """Check if the current project is ABAP (closed-service, no sandbox needed)."""
    import json
    try:
        plan = json.loads(state.get('plan', '{}'))
        if plan.get('tech_stack', {}).get('language', '').lower() == 'abap':
            return True
    except Exception:
        pass
    tech_stack = state.get('tech_stack', {})
    if isinstance(tech_stack, dict) and tech_stack.get('language', '').lower() == 'abap':
        return True
    return False


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
    if retries >= 3 or state.get('execute_retry_count', 0) >= 3:
        logger.info(
            "retry_threshold_return_to_plan",
            session_id=state.get('session_id', ''),
            retries=retries,
            execute_retry_count=state.get('execute_retry_count', 0),
        )
        return 'return_to_plan'

    # Default: retry implementation with error context
    return 'error'


def route_after_validate(state: AgentState) -> str:
    obs = state.get('last_obs')
    if obs and getattr(obs, 'app_started', False):
        return 'pass'
    if state.get('validate_retry_count', 0) >= 3:
        return 'replan'
    return 'fail'


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


def _log_node_trace(node_name: str, state_before: AgentState, state_after: AgentState):
    logger.info(
        "node_execution_trace",
        session_id=state_after.get("session_id", ""),
        node=node_name,
        status_before=state_before.get("status"),
        status_after=state_after.get("status"),
        judge_attempts=state_after.get("judge_attempts", 0),
        retries=state_after.get("retries", 0),
        modified_files_count=len(state_after.get("modified_files", []) or [])
    )

async def plan_bootstrap_node_wrapped(state: AgentState) -> AgentState:
    if "node_exception" in state:
        del state["node_exception"]
    new_state = await plan_bootstrap_node(state)
    if "node_exception" in new_state:
        del new_state["node_exception"]
    verifier = StageVerifier()
    res = verifier.verify("bootstrap", new_state)
    next_node = RoutingDecisionEngine.route("bootstrap", res, new_state)
    node_to_status = {
        "plan_bootstrap": "plan",
        "architecture_plan": "architecture",
        "error": "error"
    }
    new_state["status"] = cast(Any, node_to_status.get(next_node, new_state.get("status", "architecture")))
    _log_node_trace("plan_bootstrap", state, new_state)
    return new_state

async def architecture_plan_node_wrapped(state: AgentState) -> AgentState:
    if "node_exception" in state:
        del state["node_exception"]
    new_state = await architecture_plan_node(state)
    if "node_exception" in new_state:
        del new_state["node_exception"]
    verifier = StageVerifier()
    res = verifier.verify("architecture", new_state)
    next_node = RoutingDecisionEngine.route("architecture", res, new_state)
    node_to_status = {
        "architecture_plan": "architecture",
        "research": "research",
        "error": "error"
    }
    new_state["status"] = cast(Any, node_to_status.get(next_node, new_state.get("status", "research")))
    return new_state

async def research_node_wrapped(state: AgentState) -> AgentState:
    if "node_exception" in state:
        del state["node_exception"]
    new_state = await research_node(state)
    if "node_exception" in new_state:
        del new_state["node_exception"]
    verifier = StageVerifier()
    res = verifier.verify("research", new_state)
    next_node = RoutingDecisionEngine.route("research", res, new_state)
    node_to_status = {
        "research": "research",
        "setup_environment": "setup_env",
        "error": "error"
    }
    new_state["status"] = cast(Any, node_to_status.get(next_node, new_state.get("status", "setup_env")))
    return new_state

async def setup_environment_node_wrapped(state: AgentState) -> AgentState:
    try:
        new_state = await setup_environment_node(state)
        # Clear any previous node exception if successful
        if "node_exception" in new_state:
            del new_state["node_exception"]
    except Exception as e:
        logger.error("setup_environment_node_exception", session_id=state.get("session_id"), error=str(e))
        new_state = state.copy()
        new_state["node_exception"] = {
            "type": type(e).__name__,
            "message": str(e)
        }
        
    verifier = StageVerifier()
    res = verifier.verify("setup", new_state)
    next_node = RoutingDecisionEngine.route("setup", res, new_state)
    node_to_status = {
        "setup_environment": "setup_env",
        "plan_detail": "plan_detail",
        "error": "error"
    }
    new_state["status"] = cast(Any, node_to_status.get(next_node, new_state.get("status", "plan_detail")))
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
    new_state["status"] = cast(Any, node_to_status.get(next_node, new_state.get("status", "judge")))
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
        new_state["status"] = cast(Any, node_to_status.get(next_node, new_state.get("status", "execute")))
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
    # ABAP bypass: skip environment setup (closed SAP service)
    if _is_abap_project(state):
        return "plan_refine"
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
    return "judge_structural_check"

# All valid status values that subagent routing functions may return
_VALID_SUBAGENT_ROUTES = frozenset({
    'backend_subagent', 'frontend_subagent', 'contract_check', 'contract_structural_check', 'merge',
    'execute', 'execute_structural_check', 'validate', 'validate_structural_check', 'judge_structural_check', 'error',
})

def route_after_judge_structural(state: AgentState) -> str:
    if state.get("judge_structural_ok", False):
        return "judge"
    return "plan_refine"

def route_after_supervisor(state: AgentState) -> str:
    subagents = state.get('subagents_needed', [])
    if "backend" in subagents:
        return 'backend_subagent'
    elif "frontend" in subagents:
        return 'frontend_subagent'
    return 'merge'

def route_after_backend(state: AgentState) -> str:
    if state.get('status') == 'error':
        return 'error'
    subagents = state.get('subagents_needed', [])
    if "frontend" in subagents:
        return 'frontend_subagent'
    return 'contract_structural_check'

def route_after_frontend(state: AgentState) -> str:
    if state.get('status') == 'error':
        return 'error'
    return 'contract_structural_check'

def route_after_contract_structural(state: AgentState) -> str:
    if state.get('contract_structural_ok', False):
        return 'contract_check'
    return 'frontend_subagent'

def route_after_execute_structural(state: AgentState) -> str:
    if state.get('execute_structural_ok', False):
        return 'execute'
    return 'supervisor'

def route_after_validate_structural(state: AgentState) -> str:
    if state.get('validate_structural_ok', False):
        return 'validate'
    return 'execute'


def route_subagents(state: AgentState) -> str:
    """
    Route between subagent nodes based on status.
    Returns END for ABAP done/validate or unrecognized states (fail-safe).
    """
    status = state.get("status", "error")
    # ABAP bypass: merge → done → END (skip execute/validate entirely)
    if status == "done":
        return END
    if status == "validate":
        try:
            import json as _json
            plan = _json.loads(state.get('plan', '{}'))
            if plan.get('tech_stack', {}).get('language') == 'abap':
                return END
        except Exception:
            pass
    # Guard: validate that status is a known route target
    if status in _VALID_SUBAGENT_ROUTES:
        return status
    # Unknown status — log and terminate safely instead of crashing
    logger.error(
        "route_subagents_unknown_status",
        status=status,
        session_id=state.get('session_id', ''),
    )
    return END



async def error_handler_node(state: AgentState) -> AgentState:
    """
    Error Handler Node — sends a clear error message to the WebSocket
    before terminating the pipeline.
    
    Without this, 'error' status routes directly to END, which silently
    closes the WebSocket with no explanation to the user.
    """
    from .state_manager import merge_state_updates
    from langchain_core.messages import AIMessage
    
    session_id = state.get('session_id', '')
    plan_error = state.get('plan_error', '')
    last_error_analysis = state.get('last_error_analysis', '')
    error_history = state.get('error_history') or []
    
    # Build a user-friendly error summary
    error_parts = []
    
    node_exception = state.get('node_exception')
    if node_exception and isinstance(node_exception, dict):
        error_parts.append(f"{node_exception.get('type')}: {node_exception.get('message')}")
        
    if plan_error:
        error_parts.append(f"Planning Error: {plan_error}")
    if last_error_analysis:
        error_parts.append(f"Last Error: {str(last_error_analysis)[:500]}")
    if error_history:
        last = error_history[-1] if isinstance(error_history[-1], dict) else {}
        error_parts.append(
            f"Category: {last.get('category', 'unknown')}, "
            f"Severity: {last.get('severity', 'unknown')}"
        )
    
    error_msg = '\n'.join(error_parts) if error_parts else 'An unrecoverable error occurred.'
    
    logger.error(
        "pipeline_terminated_by_error_handler",
        session_id=session_id,
        error_summary=error_msg[:300],
    )
    
    # Notify via WebSocket
    try:
        from agent.observability import ObservabilityManager
        ObservabilityManager().log(
            session_id=session_id,
            agent_name="Error Handler",
            event_type="activity",
            description=f"Pipeline terminated: {error_msg[:200]}",
            status="error",
            metadata={"task": "Error recovery", "progress": 100, "status": "error"}
        )
    except Exception:
        pass
    
    updates = {
        'status': 'error',
        'messages': [
            AIMessage(content=f"[Pipeline Error] The build was stopped due to an error:\n{error_msg}")
        ],
    }
    return merge_state_updates(state, updates)


async def build_graph(checkpointer=None):
    """
    Build and compile the LangGraph state machine.
    
    Two-Phase Planning Flow:
      plan_bootstrap → architecture → research → setup_environment (runs scaffold)
                    → plan_refine (re-indexes workspace, generates file steps)
                    → judge → supervisor → subagents → execute → validate → END
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
    g.add_node('judge_structural_check', judge_structural_check)
    
    # Subagent Supervisor Nodes
    g.add_node('supervisor', supervisor_node)
    g.add_node('backend_subagent', backend_subagent_node)
    g.add_node('frontend_subagent', frontend_subagent_node)
    g.add_node('contract_check', contract_check_node)
    g.add_node('contract_structural_check', contract_structural_check)
    g.add_node('merge', merge_workspace_node)
    
    g.add_node('execute', execute_node_wrapped)
    g.add_node('execute_structural_check', execute_structural_check)
    g.add_node('validate', validate_node)
    g.add_node('validate_structural_check', validate_structural_check)
    g.add_node('error_handler', error_handler_node)

    def route_start(state: AgentState) -> str:
        status = state.get("status", "plan")
        mapping = {
            "plan": "plan_bootstrap",
            "architecture": "architecture_plan",
            "research": "research",
            "setup_env": "setup_environment",
            "plan_refine": "plan_refine",
            "plan_detail": "plan_refine",  # Alias for plan_detail status
            "judge": "judge",
            "judge_structural": "judge_structural_check",
            "judge_structural_check": "judge_structural_check",
            "implement": "supervisor",
            "supervisor": "supervisor",
            "backend_subagent": "backend_subagent",
            "frontend_subagent": "frontend_subagent",
            "contract_check": "contract_check",
            "contract_structural": "contract_structural_check",
            "contract_structural_check": "contract_structural_check",
            "merge": "merge",
            "execute": "execute",
            "execute_structural": "execute_structural_check",
            "execute_structural_check": "execute_structural_check",
            "validate": "validate",
            "validate_structural": "validate_structural_check",
            "validate_structural_check": "validate_structural_check",
            "error": "error_handler",  # Route to error handler instead of silent END
            "done": END,
        }
        return mapping.get(status, "plan_bootstrap")

    # Flow: plan_bootstrap → architecture → research → setup_environment → plan_refine → judge
    g.set_conditional_entry_point(route_start, {
        "plan_bootstrap": "plan_bootstrap",
        "architecture_plan": "architecture_plan",
        "research": "research",
        "setup_environment": "setup_environment",
        "plan_refine": "plan_refine",
        "judge": "judge",
        "judge_structural_check": "judge_structural_check",
        "supervisor": "supervisor",
        "backend_subagent": "backend_subagent",
        "frontend_subagent": "frontend_subagent",
        "contract_check": "contract_check",
        "contract_structural_check": "contract_structural_check",
        "merge": "merge",
        "execute": "execute",
        "execute_structural_check": "execute_structural_check",
        "validate": "validate",
        "validate_structural_check": "validate_structural_check",
        "error_handler": "error_handler",
        END: END,
    })
    
    g.add_conditional_edges('plan_bootstrap', route_after_bootstrap, {
        'plan_bootstrap': 'plan_bootstrap',
        'architecture_plan': 'architecture_plan',
        'error': 'error_handler',
    })
    g.add_conditional_edges('architecture_plan', route_after_architecture, {
        'architecture_plan': 'architecture_plan',
        'research': 'research',
        'error': 'error_handler',
    })
    g.add_conditional_edges('research', route_after_research, {
        'research': 'research',
        'setup_environment': 'setup_environment',
        'plan_refine': 'plan_refine',         # ABAP bypass: skip setup_env
        'error': 'error_handler',
    })
    g.add_conditional_edges('setup_environment', route_after_setup, {
        'setup_environment': 'setup_environment',
        'plan_refine': 'plan_refine',
        'error': 'error_handler',
    })
    g.add_conditional_edges('plan_refine', route_after_refine, {
        'plan_refine': 'plan_refine',
        'judge_structural_check': 'judge_structural_check',
        'error': 'error_handler',
    })
    g.add_conditional_edges('judge_structural_check', route_after_judge_structural, {
        'judge': 'judge',
        'plan_refine': 'plan_refine',
    })

    # Judge routes:
    #   - 'supervisor': plan approved, start coding (new subagent flow)
    #   - 'plan_refine': rejected, re-generate refine steps (scaffold already done)
    #   - 'architecture_plan': max judge attempts exceeded, trigger architectural re-planning
    #   - 'error_handler': on unhandled exception
    g.add_conditional_edges('judge', route_after_judge, {
        'plan_refine': 'plan_refine',
        'architecture_plan': 'architecture_plan',
        'supervisor': 'supervisor',
    })

    # Subagent Supervisor Routing - Sequential Conditional Dispatch (No Send / Fan-out)
    g.add_conditional_edges('supervisor', route_after_supervisor, {
        'backend_subagent': 'backend_subagent',
        'frontend_subagent': 'frontend_subagent',
        'merge': 'merge',
    })
    g.add_conditional_edges('backend_subagent', route_after_backend, {
        'frontend_subagent': 'frontend_subagent',
        'contract_structural_check': 'contract_structural_check',
        'error': 'error_handler',
    })
    g.add_conditional_edges('frontend_subagent', route_after_frontend, {
        'contract_structural_check': 'contract_structural_check',
        'error': 'error_handler',
    })
    g.add_conditional_edges('contract_structural_check', route_after_contract_structural, {
        'contract_check': 'contract_check',
        'frontend_subagent': 'frontend_subagent',
    })
    g.add_conditional_edges('contract_check', route_subagents, {
        'merge': 'merge',
        'frontend_subagent': 'frontend_subagent',     # Retry loop on semantic mismatch
        'error': 'error_handler',
        END: END,
    })
    g.add_conditional_edges('merge', route_subagents, {
        'execute': 'execute_structural_check',
        'error': 'error_handler',
        END: END,
    })

    g.add_conditional_edges('execute_structural_check', route_after_execute_structural, {
        'execute': 'execute',
        'supervisor': 'supervisor',
    })

    g.add_conditional_edges('execute', route_after_execute, {
        'error': 'supervisor',                  # fixable error → retry implementation
        'success': 'validate_structural_check', # code executed successfully → move to validation
        'max_retry': END,                       # exhausted all retries → give up
        'return_to_plan': 'plan_refine',        # fatal/repeated error or retries >= 3 → re-plan
    })

    g.add_conditional_edges('validate_structural_check', route_after_validate_structural, {
        'validate': 'validate',
        'execute': 'execute',
    })

    g.add_conditional_edges('validate', route_after_validate, {
        'pass': END,
        'fail': 'supervisor',
        'replan': 'plan_refine',
    })

    # Error handler always terminates
    g.add_edge('error_handler', END)

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
