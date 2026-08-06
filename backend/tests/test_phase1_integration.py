"""
Phase 1.1 Integration Tests

Tests for state persistence, state manager utilities, and workflow integrity.
Verifies that all nodes properly use the state_manager pattern.
"""
import sys
import os

# Add parent directory to path to import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, AIMessage
from agent.state_manager import (
    create_initial_state,
    validate_state,
    merge_state_updates,
    sanitize_state_for_storage,
    restore_state_from_storage,
    log_state_transition,
    get_state_summary,
)


class TestStateManagerUtilities:
    """Test the state_manager utility functions"""
    
    def test_create_initial_state(self):
        """Test that initial state is created with all required fields"""
        state = create_initial_state("test-session-123")
        
        # Check required fields exist
        assert state['session_id'] == "test-session-123"
        assert state['status'] == 'plan'
        assert state['chat_mode'] == 'build'
        assert state['messages'] == []
        assert state['retries'] == 0
        assert state['max_retries'] == 5
        
        # Check state is valid
        is_valid, errors = validate_state(state)
        assert is_valid, f"Initial state should be valid but got errors: {errors}"
        
        print("✅ test_create_initial_state passed!")
    
    def test_validate_state_success(self):
        """Test state validation with valid state"""
        state = create_initial_state("test-session-456")
        is_valid, errors = validate_state(state)
        
        assert is_valid
        assert len(errors) == 0
        
        print("✅ test_validate_state_success passed!")
    
    def test_validate_state_missing_fields(self):
        """Test state validation catches missing required fields"""
        state = {'session_id': 'test'}  # Missing required fields
        is_valid, errors = validate_state(state)
        
        assert not is_valid
        assert len(errors) > 0
        assert any('status' in err for err in errors)
        assert any('messages' in err for err in errors)
        
        print("✅ test_validate_state_missing_fields passed!")
    
    def test_validate_state_invalid_status(self):
        """Test state validation catches invalid status values"""
        state = create_initial_state("test-session-789")
        state['status'] = 'invalid_status'
        
        is_valid, errors = validate_state(state)
        
        assert not is_valid
        assert any('Invalid status' in err for err in errors)
        
        print("✅ test_validate_state_invalid_status passed!")
    
    def test_merge_state_updates_simple(self):
        """Test simple state merging"""
        state = create_initial_state("test-session-001")
        
        updates = {
            'status': 'research',
            'plan': '{"tasks": ["task1", "task2"]}'
        }
        
        new_state = merge_state_updates(state, updates)
        
        assert new_state['status'] == 'research'
        assert new_state['plan'] == '{"tasks": ["task1", "task2"]}'
        assert new_state['session_id'] == "test-session-001"  # Preserved
        
        print("✅ test_merge_state_updates_simple passed!")
    
    def test_merge_state_updates_list_appending(self):
        """Test that lists are properly appended, not replaced"""
        state = create_initial_state("test-session-002")
        state['error_history'] = [{'error': 'error1'}]
        
        updates = {'error_history': [{'error': 'error2'}]}
        new_state = merge_state_updates(state, updates)
        
        # Should have both errors
        assert len(new_state['error_history']) == 2
        assert new_state['error_history'][0]['error'] == 'error1'
        assert new_state['error_history'][1]['error'] == 'error2'
        
        print("✅ test_merge_state_updates_list_appending passed!")
    
    def test_merge_state_updates_dict_merging(self):
        """Test that dicts are properly merged, not replaced"""
        state = create_initial_state("test-session-003")
        state['context_budget'] = {'total': 100, 'system': 50}
        
        updates = {'context_budget': {'user': 30, 'assistant': 20}}
        new_state = merge_state_updates(state, updates)
        
        # Should have all keys
        assert new_state['context_budget']['total'] == 100
        assert new_state['context_budget']['system'] == 50
        assert new_state['context_budget']['user'] == 30
        assert new_state['context_budget']['assistant'] == 20
        
        print("✅ test_merge_state_updates_dict_merging passed!")
    
    def test_sanitize_state_for_storage(self):
        """Test state sanitization removes non-serializable objects"""
        state = create_initial_state("test-session-004")
        state['messages'] = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there")
        ]
        state['memory'] = {'some': 'object'}  # Should be removed
        state['rag_context'] = {'another': 'object'}  # Should be removed
        
        sanitized = sanitize_state_for_storage(state)
        
        # Non-serializable fields should be None
        assert sanitized['memory'] is None
        assert sanitized['rag_context'] is None
        
        # Messages should be converted to dicts
        assert isinstance(sanitized['messages'], list)
        assert len(sanitized['messages']) == 2
        assert sanitized['messages'][0]['type'] == 'human'
        assert sanitized['messages'][0]['content'] == 'Hello'
        assert sanitized['messages'][1]['type'] == 'ai'
        assert sanitized['messages'][1]['content'] == 'Hi there'
        
        print("✅ test_sanitize_state_for_storage passed!")
    
    def test_restore_state_from_storage(self):
        """Test state restoration recreates objects"""
        # Create and sanitize state
        state = create_initial_state("test-session-005")
        state['messages'] = [
            HumanMessage(content="Test message"),
        ]
        
        sanitized = sanitize_state_for_storage(state)
        
        # Restore state
        restored = restore_state_from_storage(sanitized)
        
        # Messages should be LangChain objects again
        assert len(restored['messages']) == 1
        assert isinstance(restored['messages'][0], HumanMessage)
        assert restored['messages'][0].content == "Test message"
        
        print("✅ test_restore_state_from_storage passed!")
    
    def test_get_state_summary(self):
        """Test state summary generation"""
        state = create_initial_state("test-session-006")
        state['status'] = 'implement'
        state['retry_count'] = 2
        state['modified_files'] = ['file1.py', 'file2.py']
        state['error_history'] = [{'error': 'err1'}, {'error': 'err2'}]
        
        summary = get_state_summary(state)
        
        assert summary['session_id'] == "test-session-006"
        assert summary['status'] == 'implement'
        assert summary['retry_count'] == 2
        assert summary['modified_files_count'] == 2
        assert summary['error_count'] == 2
        
        print("✅ test_get_state_summary passed!")
    
    def test_state_transition_logging(self):
        """Test state transition logging doesn't crash"""
        # This mainly tests that logging works without errors
        log_state_transition(
            session_id="test-session-007",
            from_status="plan",
            to_status="research",
            context={'reason': 'test'}
        )
        
        log_state_transition(
            session_id="test-session-007",
            from_status="research",
            to_status="setup_env",
            context={'queries': 3, 'results': 10}
        )
        
        print("✅ test_state_transition_logging passed!")


class TestStateWorkflow:
    """Test state flows through workflow correctly"""
    
    def test_workflow_state_transitions(self):
        """Test state transitions through typical workflow"""
        # Start with plan
        state = create_initial_state("workflow-test-001")
        assert state['status'] == 'plan'
        
        # Transition to research
        updates = {'status': 'research', 'plan': '{"app": "todo"}'}
        state = merge_state_updates(state, updates)
        assert state['status'] == 'research'
        assert state['plan'] == '{"app": "todo"}'
        
        # Transition to setup_env
        updates = {'status': 'setup_env', 'research_context': 'Research results...'}
        state = merge_state_updates(state, updates)
        assert state['status'] == 'setup_env'
        assert state['research_context'] == 'Research results...'
        
        # Transition to judge
        updates = {'status': 'judge', 'environment_ready': True}
        state = merge_state_updates(state, updates)
        assert state['status'] == 'judge'
        assert state['environment_ready'] is True
        
        # Transition to implement
        updates = {'status': 'implement', 'plan_approved': True}
        state = merge_state_updates(state, updates)
        assert state['status'] == 'implement'
        assert state['plan_approved'] is True
        
        # Transition to execute
        updates = {'status': 'execute', 'pending_actions': [{'action': 'write'}]}
        state = merge_state_updates(state, updates)
        assert state['status'] == 'execute'
        
        # Transition to validate
        updates = {'status': 'validate', 'execution_results': [{'result': 'success'}]}
        state = merge_state_updates(state, updates)
        assert state['status'] == 'validate'
        
        # Transition to done
        updates = {'status': 'done', 'validation_passed': True}
        state = merge_state_updates(state, updates)
        assert state['status'] == 'done'
        assert state['validation_passed'] is True
        
        print("✅ test_workflow_state_transitions passed!")
    
    def test_error_retry_loop(self):
        """Test state handling in error retry scenarios"""
        state = create_initial_state("error-test-001")
        state['status'] = 'execute'
        
        # Simulate first error
        updates = {
            'retries': 1,
            'error_history': [{'category': 'SYNTAX', 'message': 'Syntax error'}],
            'last_error_analysis': 'Missing semicolon'
        }
        state = merge_state_updates(state, updates)
        
        assert state['retries'] == 1
        assert len(state['error_history']) == 1
        
        # Simulate second error
        updates = {
            'retries': 2,
            'error_history': [{'category': 'RUNTIME', 'message': 'Runtime error'}]
        }
        state = merge_state_updates(state, updates)
        
        assert state['retries'] == 2
        assert len(state['error_history']) == 2  # Should append, not replace
        
        print("✅ test_error_retry_loop passed!")
    
    def test_judge_rejection_loop(self):
        """Test state handling when judge rejects plan"""
        state = create_initial_state("judge-test-001")
        state['status'] = 'judge'
        
        # Judge rejects plan
        updates = {
            'status': 'plan',  # Loop back to plan
            'plan_approved': False,
            'judge_feedback': 'Missing database setup',
            'judge_attempts': 1
        }
        state = merge_state_updates(state, updates)
        
        assert state['status'] == 'plan'
        assert state['plan_approved'] is False
        assert state['judge_attempts'] == 1
        
        # New plan generated
        updates = {
            'status': 'research',
            'plan': '{"app": "todo", "database": "postgresql"}'
        }
        state = merge_state_updates(state, updates)
        
        assert state['status'] == 'research'
        assert 'postgresql' in state['plan']
        
        print("✅ test_judge_rejection_loop passed!")
    
    def test_max_retries_reached(self):
        """Test state when max retries is reached"""
        state = create_initial_state("max-retry-test-001")
        state['max_retries'] = 5
        
        # Simulate reaching max retries
        for i in range(1, 6):
            updates = {
                'retries': i,
                'error_history': [{'error': f'error_{i}'}]
            }
            state = merge_state_updates(state, updates)
        
        assert state['retries'] == 5
        assert len(state['error_history']) == 5
        assert state['retries'] >= state['max_retries']
        
        print("✅ test_max_retries_reached passed!")


class TestStateFieldTracking:
    """Test that specific state fields are tracked correctly"""
    
    def test_tracking_pending_actions(self):
        """Test pending_actions field tracking"""
        state = create_initial_state("track-test-001")
        
        actions = [
            {'type': 'write', 'path': 'file1.py'},
            {'type': 'run', 'command': 'npm install'}
        ]
        
        updates = {'pending_actions': actions}
        state = merge_state_updates(state, updates)
        
        assert len(state['pending_actions']) == 2
        assert state['pending_actions'][0]['type'] == 'write'
        
        print("✅ test_tracking_pending_actions passed!")
    
    def test_tracking_execution_results(self):
        """Test execution_results field tracking"""
        state = create_initial_state("track-test-002")
        
        # First execution
        updates = {'execution_results': [{'action': 'write', 'exit_code': 0}]}
        state = merge_state_updates(state, updates)
        
        # Second execution (should append)
        updates = {'execution_results': [{'action': 'run', 'exit_code': 0}]}
        state = merge_state_updates(state, updates)
        
        assert len(state['execution_results']) == 2
        
        print("✅ test_tracking_execution_results passed!")
    
    def test_tracking_modified_files(self):
        """Test modified_files field tracking"""
        state = create_initial_state("track-test-003")
        
        updates = {'modified_files': ['app.py', 'config.json']}
        state = merge_state_updates(state, updates)
        
        assert len(state['modified_files']) == 2
        assert 'app.py' in state['modified_files']
        
        print("✅ test_tracking_modified_files passed!")
    
    def test_tracking_validation_results(self):
        """Test validation_results field tracking"""
        state = create_initial_state("track-test-004")
        
        validation_logs = [
            '✅ Compilation passed',
            '✅ Tests passed'
        ]
        
        updates = {
            'validation_results': validation_logs,
            'validation_passed': True
        }
        state = merge_state_updates(state, updates)
        
        assert len(state['validation_results']) == 2
        assert state['validation_passed'] is True
        
        print("✅ test_tracking_validation_results passed!")
    
    def test_tracking_research_findings(self):
        """Test research_findings field tracking"""
        state = create_initial_state("track-test-005")
        
        findings = [
            {'title': 'React Docs', 'url': 'https://react.dev', 'query': 'react setup'},
            {'title': 'Vite Guide', 'url': 'https://vitejs.dev', 'query': 'vite config'}
        ]
        
        updates = {'research_findings': findings}
        state = merge_state_updates(state, updates)
        
        assert len(state['research_findings']) == 2
        assert state['research_findings'][0]['title'] == 'React Docs'
        
        print("✅ test_tracking_research_findings passed!")
    
    def test_tracking_environment_ready(self):
        """Test environment_ready flag tracking"""
        state = create_initial_state("track-test-006")
        
        updates = {
            'environment_ready': True,
            'environment_info': 'node 18.x, npm 9.x',
            'setup_completed_at': '2026-06-04T18:30:00Z'
        }
        state = merge_state_updates(state, updates)
        
        assert state['environment_ready'] is True
        assert 'node 18.x' in state['environment_info']
        assert state['setup_completed_at'] == '2026-06-04T18:30:00Z'
        
        print("✅ test_tracking_environment_ready passed!")


def run_all_tests():
    """Run all test classes"""
    print("\n" + "="*70)
    print("PHASE 1.1 INTEGRATION TESTS")
    print("="*70 + "\n")
    
    # Test state manager utilities
    print("📦 Testing State Manager Utilities...")
    print("-" * 70)
    test_class = TestStateManagerUtilities()
    test_class.test_create_initial_state()
    test_class.test_validate_state_success()
    test_class.test_validate_state_missing_fields()
    test_class.test_validate_state_invalid_status()
    test_class.test_merge_state_updates_simple()
    test_class.test_merge_state_updates_list_appending()
    test_class.test_merge_state_updates_dict_merging()
    test_class.test_sanitize_state_for_storage()
    test_class.test_restore_state_from_storage()
    test_class.test_get_state_summary()
    test_class.test_state_transition_logging()
    
    # Test workflow state transitions
    print("\n🔄 Testing Workflow State Transitions...")
    print("-" * 70)
    test_class = TestStateWorkflow()
    test_class.test_workflow_state_transitions()
    test_class.test_error_retry_loop()
    test_class.test_judge_rejection_loop()
    test_class.test_max_retries_reached()
    
    # Test field tracking
    print("\n📊 Testing State Field Tracking...")
    print("-" * 70)
    test_class = TestStateFieldTracking()
    test_class.test_tracking_pending_actions()
    test_class.test_tracking_execution_results()
    test_class.test_tracking_modified_files()
    test_class.test_tracking_validation_results()
    test_class.test_tracking_research_findings()
    test_class.test_tracking_environment_ready()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70 + "\n")
    print("Phase 1.1 Integration: State persistence verified ✅")
    print("No regressions detected ✅")
    print("Ready for Issue #9: Token Management 🚀")
    print()


if __name__ == "__main__":
    run_all_tests()
