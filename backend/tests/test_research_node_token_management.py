"""
Test token management integration in research_node.

Validates Requirements 2.1, 2.2, 2.3, 2.4 from token-management-completion spec.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage

from agent.research_node import research_node
from agent.state import AgentState


@pytest.mark.anyio
async def test_research_node_includes_token_metrics():
    """
    Test that research_node includes token_count and context_budget in state updates.
    
    **Validates: Requirements 2.1, 2.3**
    """
    # Arrange
    mock_state: AgentState = {
        'session_id': 'test-session-123',
        'status': 'research',
        'plan': '{"tech_stack": {"frontend": "React", "backend": "FastAPI"}}',
        'llm_profile': {
            'provider': 'groq',
            'model': 'llama-3.3-70b-versatile'
        },
        'messages': []
    }
    
    # Mock search results
    mock_search_result = MagicMock()
    mock_search_result.title = "React Documentation"
    mock_search_result.url = "https://react.dev"
    mock_search_result.snippet = "React is a JavaScript library for building user interfaces"
    mock_search_result.content = "React documentation content here"
    
    mock_search_response = MagicMock()
    mock_search_response.results = [mock_search_result]
    mock_search_response.error = None
    
    # Mock LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Research synthesis: Use create-react-app for React setup"
    
    # Mock dependencies
    with patch('agent.research_node.generate_research_queries') as mock_queries, \
         patch('agent.research_node.search_and_extract') as mock_search, \
         patch('agent.research_node._resolve_research_llm') as mock_llm_factory:
        
        mock_queries.return_value = ["React setup guide"]
        mock_search.return_value = mock_search_response
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_llm_factory.return_value = mock_llm
        
        # Act
        result_state = await research_node(mock_state)
    
    # Assert
    assert 'token_count' in result_state, "research_node should include token_count in state updates"
    assert 'context_budget' in result_state, "research_node should include context_budget in state updates"
    
    # Verify token_count is a number
    assert isinstance(result_state['token_count'], int), "token_count should be an integer"
    assert result_state['token_count'] > 0, "token_count should be positive"
    
    # Verify context_budget structure
    budget = result_state['context_budget']
    assert isinstance(budget, dict), "context_budget should be a dictionary"
    assert 'model' in budget, "context_budget should include model"
    assert 'max_tokens' in budget, "context_budget should include max_tokens"
    assert 'workspace_context' in budget, "context_budget should include workspace_context allocation"
    
    # Verify research was completed
    assert 'research_context' in result_state, "research_node should generate research_context"
    assert result_state['status'] == 'setup_env', "research_node should transition to setup_env status"


@pytest.mark.anyio
async def test_research_node_truncates_large_search_text():
    """
    Test that research_node truncates search text exceeding workspace context budget.
    
    **Validates: Requirement 2.2**
    """
    # Arrange
    mock_state: AgentState = {
        'session_id': 'test-session-456',
        'status': 'research',
        'plan': '{"tech_stack": {"frontend": "Vue"}}',
        'llm_profile': {
            'provider': 'groq',
            'model': 'llama-3.1-8b-instant'
        },
        'messages': []
    }
    
    # Mock search results with very large content
    mock_search_result = MagicMock()
    mock_search_result.title = "Vue Documentation"
    mock_search_result.url = "https://vuejs.org"
    mock_search_result.snippet = "Vue.js framework"
    mock_search_result.content = "X" * 50000  # Very large content
    
    mock_search_response = MagicMock()
    mock_search_response.results = [mock_search_result] * 10  # Multiple large results
    mock_search_response.error = None
    
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Vue setup instructions"
    
    with patch('agent.research_node.generate_research_queries') as mock_queries, \
         patch('agent.research_node.search_and_extract') as mock_search, \
         patch('agent.research_node._resolve_research_llm') as mock_llm_factory, \
         patch('agent.research_node.logger') as mock_logger:
        
        mock_queries.return_value = ["Vue setup"]
        mock_search.return_value = mock_search_response
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_llm_factory.return_value = mock_llm
        
        # Act
        result_state = await research_node(mock_state)
    
    # Assert
    # Verify truncation was logged
    truncation_logged = any(
        'research_text_truncated' in str(call)
        for call in mock_logger.info.call_args_list
    )
    assert truncation_logged, "Should log truncation event when search text is too large"
    
    # Verify state includes token metrics
    assert 'token_count' in result_state
    assert 'context_budget' in result_state


@pytest.mark.anyio
async def test_research_node_counts_tokens_in_search_and_context():
    """
    Test that research_node tracks token counts for search text and research context.
    
    **Validates: Requirements 2.3, 2.4**
    """
    # Arrange
    mock_state: AgentState = {
        'session_id': 'test-session-789',
        'status': 'research',
        'plan': '{"tech_stack": {"backend": "Django"}}',
        'llm_profile': {
            'provider': 'groq',
            'model': 'llama-3.3-70b-versatile'
        },
        'messages': []
    }
    
    mock_search_result = MagicMock()
    mock_search_result.title = "Django Tutorial"
    mock_search_result.url = "https://djangoproject.com"
    mock_search_result.snippet = "Django web framework"
    mock_search_result.content = "Django documentation content"
    
    mock_search_response = MagicMock()
    mock_search_response.results = [mock_search_result]
    mock_search_response.error = None
    
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Django setup: pip install django && django-admin startproject myproject"
    
    with patch('agent.research_node.generate_research_queries') as mock_queries, \
         patch('agent.research_node.search_and_extract') as mock_search, \
         patch('agent.research_node._resolve_research_llm') as mock_llm_factory, \
         patch('agent.research_node.count_tokens') as mock_count_tokens, \
         patch('agent.research_node.logger') as mock_logger:
        
        mock_queries.return_value = ["Django setup"]
        mock_search.return_value = mock_search_response
        
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_llm_factory.return_value = mock_llm
        
        # Mock token counting
        mock_count_tokens.side_effect = lambda text, model=None: len(text.split())
        
        # Act
        result_state = await research_node(mock_state)
    
    # Assert
    # Verify count_tokens was called for both search text and research context
    assert mock_count_tokens.call_count >= 2, "Should count tokens for search text and research context"
    
    # Verify the logged info includes token counts
    complete_log = [call for call in mock_logger.info.call_args_list 
                    if 'research_complete' in str(call)]
    assert len(complete_log) > 0, "Should log research completion with token stats"
    
    # Verify total_tokens is logged in state transition
    assert 'token_count' in result_state
    assert result_state['token_count'] > 0


@pytest.mark.anyio
async def test_research_node_reuses_existing_research():
    """
    Test that research_node reuses existing research context and includes token metrics.
    
    **Validates: Requirements 2.1, 2.3**
    """
    # Arrange
    existing_research = "Existing research context about React and FastAPI" * 10
    mock_state: AgentState = {
        'session_id': 'test-session-reuse',
        'status': 'research',
        'plan': '{"tech_stack": {"frontend": "React"}}',
        'research_context': existing_research,
        'llm_profile': {
            'provider': 'groq',
            'model': 'llama-3.3-70b-versatile'
        },
        'messages': []
    }
    
    # Act
    result_state = await research_node(mock_state)
    
    # Assert
    assert 'token_count' in result_state, "Should include token_count when reusing research"
    assert 'context_budget' in result_state, "Should include context_budget when reusing research"
    assert result_state['research_context'] == existing_research, "Should reuse existing research"
    assert result_state['token_count'] > 0, "Should count tokens in existing research"


@pytest.mark.anyio
async def test_research_node_uses_context_manager():
    """
    Test that research_node initializes ContextManager with correct model name.
    
    **Validates: Requirement 2.1**
    """
    # Arrange
    mock_state: AgentState = {
        'session_id': 'test-session-ctx',
        'status': 'research',
        'plan': '{"tech_stack": {"frontend": "Angular"}}',
        'llm_profile': {
            'provider': 'groq',
            'model': 'llama-3.1-8b-instant'
        },
        'messages': []
    }
    
    mock_search_response = MagicMock()
    mock_search_response.results = []
    mock_search_response.error = None
    
    with patch('agent.research_node.generate_research_queries') as mock_queries, \
         patch('agent.research_node.search_and_extract') as mock_search, \
         patch('agent.research_node.ContextManager') as mock_ctx_manager_class:
        
        mock_queries.return_value = ["Angular setup"]
        mock_search.return_value = mock_search_response
        
        # Mock ContextManager
        mock_ctx_manager = MagicMock()
        mock_ctx_manager.budget.workspace_context = 2000
        mock_ctx_manager.budget.to_dict.return_value = {
            'model': 'llama-3.1-8b-instant',
            'max_tokens': 128000,
            'workspace_context': 2000
        }
        mock_ctx_manager_class.return_value = mock_ctx_manager
        
        # Act
        result_state = await research_node(mock_state)
    
    # Assert
    # Verify ContextManager was initialized with correct model
    mock_ctx_manager_class.assert_called_once_with(model='llama-3.1-8b-instant')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
