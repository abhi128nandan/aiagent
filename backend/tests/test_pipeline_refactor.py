import asyncio
import json
import pytest
from agent.subagents import supervisor_node, contract_structural_check
from agent.judge_node import judge_structural_check
from agent.nodes import execute_structural_check, validate_structural_check
from agent.graph import (
    route_after_supervisor, route_after_backend, route_after_execute,
    route_after_validate, route_after_judge_structural, route_after_contract_structural,
    route_after_execute_structural, route_after_validate_structural
)

def test_supervisor_subagents_needed_backend_only():
    state = {
        'session_id': 'test-subagent-1',
        'tech_stack': {'backend': 'fastapi', 'frontend': 'none'}
    }
    res = asyncio.run(supervisor_node(state))
    assert res['subagents_needed'] == ['backend']
    assert res['status'] == 'backend_subagent'
    assert route_after_supervisor(res) == 'backend_subagent'
    assert route_after_backend(res) == 'contract_structural_check'

def test_supervisor_subagents_needed_frontend_only():
    state = {
        'session_id': 'test-subagent-2',
        'tech_stack': {'backend': 'none', 'frontend': 'react'}
    }
    res = asyncio.run(supervisor_node(state))
    assert res['subagents_needed'] == ['frontend']
    assert res['status'] == 'frontend_subagent'
    assert route_after_supervisor(res) == 'frontend_subagent'

def test_supervisor_subagents_needed_both():
    state = {
        'session_id': 'test-subagent-3',
        'tech_stack': {'backend': 'fastapi', 'frontend': 'react'}
    }
    res = asyncio.run(supervisor_node(state))
    assert res['subagents_needed'] == ['backend', 'frontend']
    assert res['status'] == 'backend_subagent'
    assert route_after_supervisor(res) == 'backend_subagent'
    assert route_after_backend(res) == 'frontend_subagent'

def test_judge_structural_check_short_circuit():
    # Pass an invalid JSON plan or structurally empty plan
    state = {
        'session_id': 'test-judge-struct',
        'plan': '{ invalid_json... }'
    }
    res = asyncio.run(judge_structural_check(state))
    assert res['judge_structural_ok'] == False
    assert res['plan_approved'] == False
    assert route_after_judge_structural(res) == 'plan_refine'

    # Pass valid minimal plan
    valid_plan = json.dumps({
        'overview': 'Valid plan',
        'tech_stack': {'language': 'python', 'backend': 'fastapi'},
        'environment': {'base_image': 'python:3.11', 'install_commands': ['pip install fastapi'], 'run_command': 'uvicorn main:app --host 0.0.0.0 --port 8000 &'},
        'steps': [{'id': 1, 'file_path': 'main.py', 'description': 'Init app'}],
        'api_contract': []
    })
    state_valid = {'session_id': 'test-judge-struct-valid', 'plan': valid_plan}
    res_valid = asyncio.run(judge_structural_check(state_valid))
    assert res_valid['judge_structural_ok'] == True
    assert route_after_judge_structural(res_valid) == 'judge'

def test_contract_structural_check_short_circuit():
    # Contract defines endpoint that is nowhere in frontend files
    state = {
        'session_id': 'test-contract-struct',
        'api_contract': json.dumps([{'endpoint': '/api/v1/users', 'method': 'GET'}]),
        'workspace_summary': '',
        'files': {'src/App.jsx': 'const x = 1;'},
        'frontend_retries': 0
    }
    res = asyncio.run(contract_structural_check(state))
    assert res['contract_structural_ok'] == False
    assert route_after_contract_structural(res) == 'frontend_subagent'

    # Contract matches
    state_ok = {
        'session_id': 'test-contract-struct-ok',
        'api_contract': json.dumps([{'endpoint': '/api/v1/users', 'method': 'GET'}]),
        'files': {'src/App.jsx': 'fetch("/api/v1/users")'},
        'frontend_retries': 0
    }
    res_ok = asyncio.run(contract_structural_check(state_ok))
    assert res_ok['contract_structural_ok'] == True
    assert route_after_contract_structural(res_ok) == 'contract_check'

def test_execute_structural_check_short_circuit():
    class FailedObs:
        exit_code = 1
        
    state_fail = {'session_id': '', 'last_obs': FailedObs()}
    res = asyncio.run(execute_structural_check(state_fail))
    assert res['execute_structural_ok'] == False
    assert route_after_execute_structural(res) == 'supervisor'

    class SuccessObs:
        exit_code = 0
    state_ok = {'session_id': '', 'last_obs': SuccessObs()}
    res_ok = asyncio.run(execute_structural_check(state_ok))
    assert res_ok['execute_structural_ok'] == True
    assert route_after_execute_structural(res_ok) == 'execute'

def test_validate_structural_check_abap_skip():
    # ABAP should pass structural validate without test reports
    plan_abap = json.dumps({'tech_stack': {'language': 'abap'}})
    state = {'session_id': '', 'plan': plan_abap}
    res = asyncio.run(validate_structural_check(state))
    assert res['validate_structural_ok'] == True
    assert route_after_validate_structural(res) == 'validate'

def test_execute_and_validate_retry_escalation():
    # execute retry < 3 -> supervisor
    class FailObs:
        exit_code = 1
    state_exec_under = {'execute_retry_count': 2, 'last_obs': FailObs()}
    assert route_after_execute(state_exec_under) == 'error'  # maps to 'supervisor'

    # execute retry == 3 -> plan_refine (return_to_plan)
    state_exec_max = {'execute_retry_count': 3, 'last_obs': FailObs()}
    assert route_after_execute(state_exec_max) == 'return_to_plan'

    # validate retry < 3 -> supervisor (fail)
    class ValFailObs:
        app_started = False
    state_val_under = {'validate_retry_count': 2, 'last_obs': ValFailObs()}
    assert route_after_validate(state_val_under) == 'fail'  # maps to 'supervisor'

    # validate retry == 3 -> replan (maps to plan_refine)
    state_val_max = {'validate_retry_count': 3, 'last_obs': ValFailObs()}
    assert route_after_validate(state_val_max) == 'replan'
