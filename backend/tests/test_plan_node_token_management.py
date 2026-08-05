"""
Test token management integration in plan_bootstrap_node.

The planning node must budget the ENTIRE request (SRS + workspace +
environment + judge feedback) via ContextManager.fit_request so a single
call never exceeds the model's context limit (e.g. Groq free-tier 12k).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage

from agent.nodes import plan_bootstrap_node
from agent.state import AgentState


def _mock_llm_factory_response(content: str):
    """Build an AsyncMock LLM whose pipe-invocation yields `content`."""
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm = AsyncMock(return_value=mock_response)
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    return mock_llm, mock_response


@pytest.mark.anyio
async def test_plan_bootstrap_includes_token_metrics():
    """plan_bootstrap_node must report token_count and context_budget."""
    mock_state: AgentState = {
        'session_id': 'test-session-123',
        'status': 'plan',
        'messages': [HumanMessage(content="Build a simple todo app with React and Node.js")],
        'llm_profile': {
            'provider': 'groq',
            'model': 'llama-3.3-70b-versatile'
        },
        'chat_mode': 'build'
    }

    mock_llm, _ = _mock_llm_factory_response(
        '{"project": "todo", "description": "Simple todo app", '
        '"tech_stack": {"frontend": "react", "backend": "none", "database": "none", "language": "typescript"}, '
        '"environment": {"runtime": ["node"], "system_packages": [], "global_tools": []}, '
        '"template_selected": "react-vite", "run_command": "npm run dev", "steps": []}'
    )

    with patch('agent.nodes._resolve_llm', return_value=mock_llm), \
         patch('agent.nodes._get_model_name') as mock_model_name_getter, \
         patch('agent.nodes.WorkspaceIndexer') as mock_indexer, \
         patch('agent.nodes.DockerRuntime'), \
         patch('agent.nodes._get_memory_manager'), \
         patch('agent.observability.ObservabilityManager'):
        mock_model_name_getter.side_effect = lambda state, role=None: state.get("llm_profile", {}).get("model", "")
        mock_indexer.return_value.get_ranked_context.return_value = "No existing workspace"
        result_state = await plan_bootstrap_node(mock_state)

    assert 'token_count' in result_state
    assert isinstance(result_state['token_count'], int)
    assert 'context_budget' in result_state
    budget = result_state['context_budget']
    assert isinstance(budget, dict)
    assert 'model' in budget
    assert 'max_tokens' in budget
    assert 'conversation' in budget

    assert 'plan' in result_state
    assert result_state['status'] == 'setup_env'


@pytest.mark.anyio
async def test_plan_bootstrap_fits_whole_request():
    """plan_bootstrap_node must budget ALL prompt components via fit_request."""
    mock_state: AgentState = {
        'session_id': 'test-session-456',
        'status': 'plan',
        'messages': [HumanMessage(content="Create a large SRS document " * 100)],
        'llm_profile': {
            'provider': 'groq',
            'model': 'llama-3.1-8b-instant'
        },
        'chat_mode': 'build'
    }

    mock_llm, _ = _mock_llm_factory_response(
        '{"project": "test", "description": "Large SRS test", '
        '"tech_stack": {"frontend": "react", "backend": "none", "database": "none", "language": "typescript"}, '
        '"environment": {"runtime": ["node"], "system_packages": [], "global_tools": []}, '
        '"template_selected": "react-vite", "run_command": "npm run dev", "steps": []}'
    )

    with patch('agent.nodes._resolve_llm', return_value=mock_llm), \
         patch('agent.nodes._get_model_name') as mock_model_name_getter, \
         patch('agent.nodes.ContextManager') as mock_ctx_manager_class, \
         patch('agent.nodes.WorkspaceIndexer'), \
         patch('agent.nodes.DockerRuntime'), \
         patch('agent.nodes._get_memory_manager'), \
         patch('agent.observability.ObservabilityManager'):
        mock_model_name_getter.side_effect = lambda state, role=None: state.get("llm_profile", {}).get("model", "")

        mock_ctx_manager = MagicMock()
        # fit_request must return prompt-ready components for the template
        mock_ctx_manager.fit_request.return_value = {
            'components': {
                'srs_text': 'trimmed srs',
                'workspace_context': 'trimmed workspace',
                'environment_discovery': 'env',
                'judge_feedback': '',
            },
            'messages': [HumanMessage(content="Pruned message")],
            'stats': {'request_tokens': 1000, 'over_limit': False},
        }
        mock_ctx_manager.prune_messages.return_value = [HumanMessage(content="Pruned message")]
        mock_ctx_manager.budget.to_dict.return_value = {
            'model': 'llama-3.1-8b-instant',
            'max_tokens': 128000,
            'conversation': 120000,
        }
        mock_ctx_manager_class.return_value = mock_ctx_manager

        result_state = await plan_bootstrap_node(mock_state)

    # ContextManager initialized with the model from llm_profile
    mock_ctx_manager_class.assert_called_once()
    assert 'llama-3.1-8b-instant' in str(mock_ctx_manager_class.call_args)

    # The whole request was fitted — components passed include the SRS
    mock_ctx_manager.fit_request.assert_called_once()
    fit_kwargs = mock_ctx_manager.fit_request.call_args.kwargs
    assert 'srs_text' in fit_kwargs.get('components', {})
    assert 'workspace_context' in fit_kwargs.get('components', {})

    assert result_state['status'] == 'setup_env'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
