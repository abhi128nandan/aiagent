"""
State Management Utilities

Provides state initialization, validation, and persistence helpers
for the agent workflow.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .state import AgentState
from core.logger import get_logger
from agent.checkpoint_manager import CheckpointManager
from agent.stage_checkpoint import VerificationMode

logger = get_logger(__name__)


def create_initial_state(session_id: str, llm_profile: Optional[Any] = None) -> Dict[str, Any]:
    """
    Create a new AgentState with sensible defaults
    
    Args:
        session_id: Unique session identifier
        llm_profile: LLM configuration profile
        
    Returns:
        Dictionary with initial state values
    """
    import uuid
    return {
        # Core
        'session_id': session_id,
        'trace_id': str(uuid.uuid4()),
        'stage_id': '',
        'parent_span_id': '',
        'status': 'plan',
        'chat_mode': 'build',
        'llm_profile': llm_profile,
        'messages': [],
        
        # Planning
        'plan': '{}',
        'current_task_index': 0,
        'plan_generated_at': '',
        'pending_actions': [],
        'execution_results': [],
        'modified_files': [],
        
        # Two-Phase Planning
        'planning_phase': 'bootstrap',
        'scaffold_completed': False,
        
        # Files
        'files': {},
        'locked_files': [],
        
        # Docker
        'container_id': '',
        'workspace_path': '/workspace',
        'last_obs': None,
        '_action': None,
        
        # Retry & Error
        'retries': 0,
        'retry_count': 0,
        'max_retries': 5,
        'has_execution_errors': False,
        'has_validation_errors': False,
        'validation_errors': [],
        'validation_warnings': [],
        
        # Token Management
        'token_count': 0,
        'context_budget': {},
        'context_overflow_count': 0,
        'total_tokens_processed': 0,
        'total_pruning_events': 0,
        'total_overflow_events': 0,
        'max_token_count_reached': 0,

        # Error Intelligence
        'error_history': [],
        'last_error_analysis': None,
        'internal_validation_errors': [],
        
        # Workspace
        'workspace_summary': '',
        'workspace_index': None,
        'rag_context': None,
        
        # Environment
        'environment_info': '',
        'environment_ready': False,
        'setup_completed_at': '',
        
        # Research
        'research_context': '',
        'research_findings': [],
        'needs_research': False,
        
        # Judge
        'judge_feedback': '',
        'plan_approved': False,
        'judge_attempts': 0,
        'plan_error': '',
        
        # Validation
        'validation_results': [],
        'validation_passed': False,
        'app_port': 3000,
        'health_endpoint': '/health',
        
        # Memory
        'memory': None,
        'last_prompt': '',
        'implementation_explanation': '',

        # Staged Verification & Architecture
        'architectural_plan': None,
        'architecture_phase': 'NotStarted',
        'stage_checkpoints': CheckpointManager.create_checkpoints(),
        'current_checkpoint': '',
        'verification_history': [],
        'verification_enabled': True,
        'verification_mode': VerificationMode.Strict,
        'stage_error_counts': {},
        'critical_failure_threshold': 3,
    }



def validate_state(state: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate state has required fields
    
    Args:
        state: State dictionary to validate
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Required fields
    required = ['session_id', 'status', 'messages', 'trace_id']
    for field in required:
        if field not in state:
            errors.append(f"Missing required field: {field}")
    
    # Type checks
    if 'session_id' in state and not isinstance(state['session_id'], str):
        errors.append("session_id must be a string")
    
    if 'status' in state:
        valid_statuses = ['plan', 'research', 'setup_env', 'judge', 'implement', 'execute', 'validate', 'done', 'error']
        if state['status'] not in valid_statuses:
            errors.append(f"Invalid status: {state['status']}")
    
    if 'retry_count' in state and state['retry_count'] < 0:
        errors.append("retry_count cannot be negative")
    
    if 'max_retries' in state and state['max_retries'] < 0:
        errors.append("max_retries cannot be negative")
    
    return (len(errors) == 0, errors)


from typing import cast
def merge_state_updates(current_state: AgentState, updates: Dict[str, Any]) -> AgentState:
    """
    Safely merge state updates into current state
    
    Args:
        current_state: Current state dictionary
        updates: Updates to apply
        
    Returns:
        Merged state dictionary
    """
    merged = current_state.copy()
    
    for key, value in updates.items():
        # Handle list appending
        if key in ['error_history', 'research_findings', 'execution_results', 'modified_files']:
            if isinstance(value, list):
                existing = merged.get(key, [])
                if isinstance(existing, list):
                    merged[key] = existing + value
                else:
                    merged[key] = value
            elif value is None:
                # None means "nothing new" — never clobber accumulated history
                continue
            else:
                merged[key] = value
        
        # Handle dict merging
        elif key in ['context_budget', 'workspace_index', 'files']:
            if isinstance(value, dict):
                existing = merged.get(key, {})
                if isinstance(existing, dict):
                    merged[key] = {**existing, **value}
                else:
                    merged[key] = value
            else:
                merged[key] = value
        
        # Direct assignment for other fields
        else:
            merged[key] = value
    
    return cast(AgentState, merged)


def sanitize_state_for_storage(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare state for database storage (remove non-serializable objects)
    
    Args:
        state: State dictionary
        
    Returns:
        Sanitized state safe for JSON storage
    """
    import copy
    sanitized = copy.deepcopy(state)
    
    # Remove non-serializable fields
    non_serializable = ['memory', 'rag_context', 'llm_profile', '_action', 'last_obs']
    for field in non_serializable:
        if field in sanitized:
            # Store type info for restoration
            if field == 'llm_profile' and sanitized[field] is not None:
                # Convert LLMProfile to dict
                profile = sanitized[field]
                if hasattr(profile, '__dict__'):
                    sanitized[field] = {
                        '_type': 'LLMProfile',
                        'provider': getattr(profile, 'provider', None),
                        'model': getattr(profile, 'model', None),
                    }
            else:
                sanitized[field] = None
    
    # Convert messages to serializable format
    if 'messages' in sanitized:
        serializable_messages = []
        for msg in sanitized['messages']:
            if hasattr(msg, 'type') and hasattr(msg, 'content'):
                serializable_messages.append({
                    'type': msg.type,
                    'content': msg.content
                })
        sanitized['messages'] = serializable_messages
    
    return sanitized


def restore_state_from_storage(stored_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Restore state from database storage (recreate objects)
    
    Args:
        stored_state: State from database
        
    Returns:
        Restored state with objects recreated
    """
    from langchain_core.messages import HumanMessage, AIMessage
    from models.llm_profile import LLMProfile
    import copy
    
    restored = copy.deepcopy(stored_state)
    
    # Restore messages
    if 'messages' in restored and isinstance(restored['messages'], list):
        restored_messages = []
        for msg in restored['messages']:
            if isinstance(msg, dict):
                msg_type = msg.get('type', 'human')
                content = msg.get('content', '')
                if msg_type == 'human':
                    restored_messages.append(HumanMessage(content=content))
                elif msg_type == 'ai':
                    restored_messages.append(AIMessage(content=content))
        restored['messages'] = restored_messages
    
    # Restore LLMProfile
    if 'llm_profile' in restored and isinstance(restored['llm_profile'], dict):
        profile_data = restored['llm_profile']
        if profile_data.get('_type') == 'LLMProfile':
            # Recreate LLMProfile object (simplified)
            restored['llm_profile'] = profile_data  # Keep as dict for now
    
    return restored


def log_state_transition(
    session_id: str,
    from_status: str,
    to_status: str,
    context: Optional[Dict[str, Any]] = None
):
    """
    Log state transitions for debugging
    
    Args:
        session_id: Session identifier
        from_status: Previous status
        to_status: New status
        context: Additional context
    """
    logger.info(
        "state_transition",
        session_id=session_id,
        from_status=from_status,
        to_status=to_status,
        context=context or {}
    )


def get_state_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a compact summary of current state for logging
    
    Args:
        state: Current state
        
    Returns:
        Summary dictionary
    """
    return {
        'session_id': state.get('session_id'),
        'status': state.get('status'),
        'retry_count': state.get('retry_count', 0),
        'max_retries': state.get('max_retries', 5),
        'has_errors': state.get('has_execution_errors', False),
        'plan_approved': state.get('plan_approved', False),
        'environment_ready': state.get('environment_ready', False),
        'token_count': state.get('token_count', 0),
        'message_count': len(state.get('messages', [])),
        'modified_files_count': len(state.get('modified_files', [])),
        'error_count': len(state.get('error_history', [])),
    }
