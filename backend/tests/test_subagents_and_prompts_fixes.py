import asyncio
import json
from agent.subagents import supervisor_node, contract_check_node
from agent.prompts import REFINE_PLAN_SCHEMA_INSTRUCTIONS

def test_supervisor_retry_reset_on_fresh_dispatch():
    # Fresh dispatch: plan_approved is True, last_obs is None
    state = {
        'session_id': 'test-1',
        'plan_approved': True,
        'last_obs': None,
        'backend_retries': 2,
        'frontend_retries': 2,
        'tech_stack': {'backend': 'python'},
        'plan': json.dumps({'api_contract': []}),
    }
    res = asyncio.run(supervisor_node(state))
    assert res['backend_retries'] == 0
    assert res['frontend_retries'] == 0

def test_supervisor_retry_persistence_on_mid_execution_loop():
    # Mid-execution loop: last_obs is present
    class DummyObs:
        exit_code = 1
    
    state = {
        'session_id': 'test-2',
        'plan_approved': True,
        'last_obs': DummyObs(),
        'backend_retries': 2,
        'frontend_retries': 1,
        'tech_stack': {'backend': 'python'},
        'plan': json.dumps({'api_contract': []}),
    }
    res = asyncio.run(supervisor_node(state))
    assert res['backend_retries'] == 2
    assert res['frontend_retries'] == 1

def test_contract_check_node_with_cached_files():
    # Verify contract check uses cached files content
    state = {
        'session_id': 'test-3',
        'api_contract': json.dumps([{'endpoint': '/api/products', 'method': 'GET'}]),
        'workspace_summary': '',
        'modified_files': ['src/App.jsx'],
        'files': {
            'src/App.jsx': 'const res = await fetch("/api/products");'
        },
        'frontend_retries': 0
    }
    res = asyncio.run(contract_check_node(state))
    assert res['contract_mismatch'] == False
    assert res['status'] == 'merge'

def test_refine_prompts_schema_instructions():
    assert '--bind 0.0.0.0' in REFINE_PLAN_SCHEMA_INSTRUCTIONS
    assert 'UNLESS explicitly instructed to correct them by the judge critique' in REFINE_PLAN_SCHEMA_INSTRUCTIONS
