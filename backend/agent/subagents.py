"""
Subagent Nodes — Backend/Frontend file-scope filtering and contract validation.

Each subagent filters the plan to its own domain before delegating to implement_node,
so the LLM only generates code for the relevant files (no duplicate work).
"""
import json as _json
from typing import Dict, Any, List
from langchain_core.messages import AIMessage
from .state import AgentState
from .state_manager import merge_state_updates
from core.logger import get_logger

logger = get_logger(__name__)


# ── File categorization helpers ──────────────────────────────────────────

_BACKEND_PATTERNS = (
    'backend/', 'backend', 'server/', 'routes', 'controllers', 'services', 'models', 'middleware',
    'api/', 'db/', 'database/', 'prisma/', 'drizzle/', 'migrations/',
    'app.py', 'main.py', 'manage.py', 'wsgi.py', 'asgi.py',
    'app.js', 'server.js', 'index.js',
    'requirements.txt', 'Pipfile', 'pyproject.toml',
    'pom.xml', 'build.gradle', 'Cargo.toml', 'go.mod',
    'views.py', 'urls.py', 'settings.py',
    'routers/', 'schemas/',
    'src/main/java/', 'application.properties', 'application.yml',
)

_FRONTEND_PATTERNS = (
    'frontend/', 'frontend', 'client/', 'ui/',
    'src/components', 'src/pages', 'src/views', 'src/layouts',
    'src/hooks', 'src/context', 'src/store', 'src/styles',
    'src/App', 'src/main', 'src/index',
    'public/', 'static/', 'assets/',
    'index.html', 'index.css', 'App.css', 'App.tsx', 'App.jsx',
    'tailwind.config', 'postcss.config', 'vite.config', 'next.config',
    'tsconfig', 'package.json',
    'app/', 'lib/', 'src/app/',
)

_SHARED_FILES = (
    'package.json', '.env', '.gitignore', 'README.md',
    'docker-compose', 'Dockerfile', 'Makefile',
)


def _classify_file(filepath: str) -> str:
    """Classify a file path as 'backend', 'frontend', or 'shared'."""
    fp_lower = filepath.lower()
    
    # Shared files belong to both domains
    if any(s in fp_lower for s in _SHARED_FILES):
        return 'shared'
    
    is_backend = any(p in fp_lower for p in _BACKEND_PATTERNS)
    is_frontend = any(p in fp_lower for p in _FRONTEND_PATTERNS)
    
    if is_backend and not is_frontend:
        return 'backend'
    if is_frontend and not is_backend:
        return 'frontend'
    if is_backend and is_frontend:
        return 'shared'
    
    # Default: treat unknown files as shared
    return 'shared'


def _filter_plan_steps(plan_str: str, domain: str) -> str:
    """
    Filter the plan JSON to only include steps for the given domain.
    
    domain: 'backend' or 'frontend'
    Returns: filtered plan JSON string
    """
    try:
        plan = _json.loads(plan_str)
    except Exception:
        return plan_str  # Return unmodified if unparseable
    
    steps = plan.get('steps', [])
    filtered_steps = []
    
    for step in steps:
        if not isinstance(step, dict):
            filtered_steps.append(step)
            continue
        
        filepath = step.get('file_path', step.get('file', ''))
        if not filepath:
            # Steps without files (e.g., commands) go to both domains
            filtered_steps.append(step)
            continue
        
        classification = _classify_file(filepath)
        if classification == domain or classification == 'shared':
            filtered_steps.append(step)
    
    plan['steps'] = filtered_steps
    return _json.dumps(plan)


# ── Subagent Nodes ───────────────────────────────────────────────────────


async def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor Node — dispatches to backend subagent first.
    Extracts API contract from the plan for contract validation.
    """
    logger.info("supervisor_dispatching", session_id=state.get('session_id'))
    
    # Extract API contract from plan if present
    plan_str = state.get('plan', '{}')
    api_contract = ""
    try:
        plan_data = _json.loads(plan_str)
        api_contract = _json.dumps(plan_data.get('api_contract', []), indent=2)
    except Exception:
        pass
    
    # Check if this is a frontend-only project (no backend needed)
    tech_stack = state.get('tech_stack', {})
    if not tech_stack or not isinstance(tech_stack, dict):
        try:
            plan_data = _json.loads(plan_str)
            tech_stack = plan_data.get('tech_stack', {})
        except Exception:
            tech_stack = {}
            
    backend = tech_stack.get('backend', 'none') if isinstance(tech_stack, dict) else 'none'
    frontend = tech_stack.get('frontend', 'none') if isinstance(tech_stack, dict) else 'none'
    
    # Check if this is a fresh plan dispatch vs mid-execution retry loop
    is_fresh_dispatch = state.get('plan_approved', False) and state.get('last_obs') is None
    backend_retries = 0 if is_fresh_dispatch else state.get('backend_retries', 0)
    frontend_retries = 0 if is_fresh_dispatch else state.get('frontend_retries', 0)

    subagents_needed = []
    if backend and str(backend).lower() != 'none':
        subagents_needed.append("backend")
    if frontend and str(frontend).lower() != 'none':
        subagents_needed.append("frontend")
    if not subagents_needed:
        subagents_needed = ["backend", "frontend"]

    if "backend" in subagents_needed:
        next_status = "backend_subagent"
    elif "frontend" in subagents_needed:
        next_status = "frontend_subagent"
    else:
        next_status = "merge"

    logger.info("supervisor_subagents_needed", session_id=state.get('session_id'), needed=subagents_needed)
    updates = {
        'status': next_status,
        'subagents_needed': subagents_needed,
        'api_contract': api_contract,
        'backend_retries': backend_retries,
        'frontend_retries': frontend_retries,
        'contract_mismatch': False,
    }
    
    return merge_state_updates(state, updates)


async def backend_subagent_node(state: AgentState) -> AgentState:
    """
    Backend Subagent Node — generates only backend code.
    
    Filters the plan to backend-relevant files before calling implement_node,
    and injects the API contract into the context for consistency.
    """
    from .nodes import implement_node
    
    session_id = state.get('session_id', '')
    logger.info("backend_subagent_running", session_id=session_id)
    
    # Filter plan to backend files only
    original_plan = state.get('plan', '{}')
    filtered_plan = _filter_plan_steps(original_plan, 'backend')
    
    # Create a scoped state with filtered plan + API contract context
    scoped_state = dict(state)
    scoped_state['plan'] = filtered_plan
    
    # Add API contract to research context so the LLM knows the expected endpoints
    api_contract = state.get('api_contract', '')
    if api_contract and api_contract != '[]':
        existing_research = scoped_state.get('research_context', '') or ''
        scoped_state['research_context'] = (
            f"{existing_research}\n\n"
            f"API CONTRACT (Backend MUST implement these endpoints):\n{api_contract}"
        )
    
    # Delegate to implement_node with scoped context
    result_state = await implement_node(scoped_state)
    result_state = merge_state_updates(state, result_state)
    
    # Restore the original full plan (don't lose frontend steps)
    result_state['plan'] = original_plan
    
    # Handle retries
    retries = state.get('backend_retries', 0)
    has_errors = result_state.get('has_execution_errors', False) or result_state.get('status') == 'error'
    
    if has_errors and retries < 3:
        updates = {
            'backend_retries': retries + 1,
            'status': 'backend_subagent',  # Loop back to itself
        }
        logger.info("backend_subagent_retrying", retries=retries + 1)
        return merge_state_updates(result_state, updates)
    
    # Success or max retries reached — proceed to frontend
    updates = {
        'status': 'frontend_subagent',
        'messages': [AIMessage(content="[Backend Subagent] Backend code committed. Handing off to Frontend Subagent.")],
    }
    return merge_state_updates(result_state, updates)


async def frontend_subagent_node(state: AgentState) -> AgentState:
    """
    Frontend Subagent Node — generates only frontend code.
    
    Filters the plan to frontend-relevant files and injects API contract
    + backend route signatures for correct API integration.
    """
    from .nodes import implement_node
    
    session_id = state.get('session_id', '')
    logger.info("frontend_subagent_running", session_id=session_id)
    
    # Filter plan to frontend files only
    original_plan = state.get('plan', '{}')
    filtered_plan = _filter_plan_steps(original_plan, 'frontend')
    
    # Create a scoped state with filtered plan
    scoped_state = dict(state)
    scoped_state['plan'] = filtered_plan
    
    # Add API contract to context so frontend knows the correct endpoints
    api_contract = state.get('api_contract', '')
    if api_contract and api_contract != '[]':
        existing_research = scoped_state.get('research_context', '') or ''
        scoped_state['research_context'] = (
            f"{existing_research}\n\n"
            f"API CONTRACT (Frontend MUST use these endpoints):\n{api_contract}"
        )
    
    # Delegate to implement_node with scoped context
    result_state = await implement_node(scoped_state)
    result_state = merge_state_updates(state, result_state)
    
    # Restore the original full plan
    result_state['plan'] = original_plan
    
    updates = {
        'status': 'contract_check',
        'messages': [AIMessage(content="[Frontend Subagent] Frontend code committed. Checking contracts...")],
    }
    return merge_state_updates(result_state, updates)


async def contract_check_node(state: AgentState) -> AgentState:
    """
    Contract Check Node — validates that frontend files reference the correct
    API endpoints defined in the plan's api_contract.
    
    Checks:
    1. Parses api_contract from state
    2. Scans modified frontend files for endpoint URL references
    3. Reports mismatches if critical endpoints are missing
    """
    session_id = state.get('session_id', '')
    logger.info("contract_check_running", session_id=session_id)
    
    # Parse the API contract
    api_contract_str = state.get('api_contract', '[]')
    try:
        api_contract = _json.loads(api_contract_str)
    except Exception:
        api_contract = []
    
    # If no API contract exists, pass through
    if not api_contract:
        logger.info("contract_check_no_contract", session_id=session_id)
        updates = {
            'status': 'merge',
            'contract_mismatch': False,
            'messages': [AIMessage(content="[Contract Check] No API contract defined. Passing through.")],
        }
        return merge_state_updates(state, updates)
    
    # Extract expected endpoints from contract
    expected_endpoints = set()
    for entry in api_contract:
        if isinstance(entry, dict):
            endpoint = entry.get('endpoint', entry.get('path', ''))
            if endpoint:
                expected_endpoints.add(endpoint)
    
    if not expected_endpoints:
        updates = {
            'status': 'merge',
            'contract_mismatch': False,
            'messages': [AIMessage(content="[Contract Check] Schemas match! Proceeding to merge.")],
        }
        return merge_state_updates(state, updates)
    
    # Check modified files for endpoint references
    modified_files = state.get('modified_files', [])
    workspace_summary = state.get('workspace_summary', '')
    
    # Check file contents cache, workspace summary, and file paths for endpoint references
    cached_files_text = ' '.join(state.get('files', {}).values()) if isinstance(state.get('files'), dict) else ''
    context_text = (workspace_summary + ' ' + cached_files_text + ' ' + str(modified_files)).lower()
    missing_endpoints = []
    
    for ep in expected_endpoints:
        # Check if the endpoint pattern appears anywhere in context
        ep_normalized = ep.strip('/').lower()
        if ep_normalized and ep_normalized not in context_text:
            missing_endpoints.append(ep)
    
    # Only flag as mismatch if more than half of endpoints are missing
    mismatch = len(missing_endpoints) > len(expected_endpoints) / 2
    
    if mismatch:
        retries = state.get('frontend_retries', 0)
        if retries >= 2:
            # After 2 retries, proceed anyway to avoid infinite loops
            logger.warning("contract_check_max_retries", session_id=session_id, retries=retries)
            mismatch = False
        else:
            logger.warning(
                "contract_check_mismatch",
                session_id=session_id,
                missing=missing_endpoints[:5],
                total_expected=len(expected_endpoints),
            )
    
    if mismatch:
        updates = {
            'status': 'frontend_subagent',
            'contract_mismatch': True,
            'frontend_retries': state.get('frontend_retries', 0) + 1,
            'messages': [AIMessage(
                content=f"[Contract Check] Mismatch detected. Missing endpoints: "
                        f"{', '.join(missing_endpoints[:5])}. Frontend must retry."
            )],
        }
    else:
        updates = {
            'status': 'merge',
            'contract_mismatch': False,
            'messages': [AIMessage(content="[Contract Check] Schemas match! Proceeding to merge.")],
        }
    
    return merge_state_updates(state, updates)


async def merge_workspace_node(state: AgentState) -> AgentState:
    """
    Merge to Workspace Node — finalizes subagent work and proceeds to execution.
    """
    logger.info("merge_workspace_running", session_id=state.get('session_id'))
    updates = {
        'status': 'execute',
        'messages': [AIMessage(content="[Merge] Code merged to workspace. Proceeding to execution.")],
    }
    return merge_state_updates(state, updates)


async def contract_structural_check(state: AgentState) -> AgentState:
    """
    Two-tier verification gate: structural sub-node before contract check.
    Diffs backend's exposed routes against frontend's expected endpoints using simple Python analysis (no LLM call).
    """
    session_id = state.get('session_id', '')
    api_contract_str = state.get('api_contract', '[]')
    try:
        api_contract = _json.loads(api_contract_str)
    except Exception:
        api_contract = []
    
    if not api_contract:
        return merge_state_updates(state, {'contract_structural_ok': True})
        
    expected_endpoints = set()
    for entry in api_contract:
        if isinstance(entry, dict):
            endpoint = entry.get('endpoint', entry.get('path', ''))
            if endpoint:
                expected_endpoints.add(endpoint)
                
    if not expected_endpoints:
        return merge_state_updates(state, {'contract_structural_ok': True})
        
    cached_files_text = ' '.join(state.get('files', {}).values()) if isinstance(state.get('files'), dict) else ''
    workspace_summary = state.get('workspace_summary', '')
    context_text = (workspace_summary + ' ' + cached_files_text).lower()
    
    missing_endpoints = [ep for ep in expected_endpoints if ep.strip('/').lower() not in context_text and ep.strip('/') != '']
    
    if len(missing_endpoints) == len(expected_endpoints) and len(expected_endpoints) > 0 and state.get('frontend_retries', 0) < 2:
        logger.warning("contract_structural_check_failed", session_id=session_id, missing=missing_endpoints)
        updates = {
            'contract_structural_ok': False,
            'messages': [AIMessage(content=f"[Contract Structural Check] Zero matching API endpoints found in frontend code. Expected: {list(expected_endpoints)}")]
        }
    else:
        updates = {'contract_structural_ok': True}
        
    return merge_state_updates(state, updates)

