import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path to import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.judge_node import judge_node
from agent.state import AgentState
from langchain_core.messages import HumanMessage, AIMessage

@pytest.mark.anyio
async def test_judge_node_abap_override_success():
    # Setup mock LLM response representing a plan rejected by LLM due to local env mismatch
    mock_response = AIMessage(content="""{
  "approved": false,
  "critique": "Some environment incompatibility or missing dev server.",
  "score": 4,
  "criteria_scores": {
    "completeness": 8,
    "compatibility": 2,
    "feasibility": 5,
    "docker": 1,
    "file_coverage": 8
  },
  "checklist_failures": ["Dev server start command is correct and runs in background"],
  "root_cause_analysis": "Incorrect dev server",
  "agent_responsible": "Detail Planner Agent"
}""")

    state: AgentState = {
        "session_id": "test-abap-session",
        "status": "judge",
        "chat_mode": "code",
        "messages": [HumanMessage(content="Build a SAP ABAP ERP program.")],
        # Contains files in all 12 designated folders
        "plan": '{"tech_stack": {"language": "abap", "frontend": "none", "backend": "abap"}, "files": ["docs/architecture.md", "packages/zcore/zcl_test.clas.abap", "dictionary/ztbl.tabl.xml", "classes/zcl_calculator.clas.abap", "reports/zprog.prog.abap", "module_pools/zprog_mp.prog.abap", "functions/zfm.fugr.abap", "forms/zadobe.pdf.xml", "cds_views/zddls.ddls.asddls", "odata/zsrv.xml", "workflows/zwf.xml", "auth/zauth.auth.xml"], "steps": []}',
        "environment_info": "Python3 and Node.js pre-installed.",
        "research_context": "",
        "judge_attempts": 0,
        "llm_profile": {
            "provider": "ollama",
            "model": "llama3.1:8b"
        }
    }

    # Patch chain.ainvoke to return our mocked LLM response
    with patch("langchain_core.runnables.base.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_response
        
        result = await judge_node(state)
        
        # Verify the overrides applied
        assert result.get("plan_approved") is True
        assert result.get("judge_score") >= 6
        assert result.get("status") == "implement"

@pytest.mark.anyio
async def test_judge_node_abap_override_failure_due_to_completeness():
    # Setup mock LLM response with low completeness
    mock_response = AIMessage(content="""{
  "approved": false,
  "critique": "Plan is incomplete, only has one file.",
  "score": 3,
  "criteria_scores": {
    "completeness": 4,
    "compatibility": 2,
    "feasibility": 5,
    "docker": 1,
    "file_coverage": 5
  },
  "checklist_failures": [],
  "root_cause_analysis": "Incomplete plan",
  "agent_responsible": "Detail Planner Agent"
}""")

    state: AgentState = {
        "session_id": "test-abap-session-fail",
        "status": "judge",
        "chat_mode": "code",
        "messages": [HumanMessage(content="Build a SAP ABAP ERP program.")],
        # Even if completeness is low, it would also be caught by missing folders check first since it only has packages/ file
        "plan": '{"tech_stack": {"language": "abap", "frontend": "none", "backend": "abap"}, "files": ["packages/zcore/zcl_test.clas.abap"], "steps": []}',
        "environment_info": "Python3 and Node.js pre-installed.",
        "research_context": "",
        "judge_attempts": 0,
        "llm_profile": {
            "provider": "ollama",
            "model": "llama3.1:8b"
        }
    }

    with patch("langchain_core.runnables.base.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_response
        
        result = await judge_node(state)
        
        # Verify that because completeness is 4 (and folders are missing), it is rejected
        assert result.get("plan_approved") is False
        assert "ABAP Plan is incomplete." in result.get("judge_feedback", "")
        assert result.get("status") == "plan"

@pytest.mark.anyio
async def test_judge_node_abap_override_missing_folders():
    # LLM says approved: true, but folders are missing in python-level check
    mock_response = AIMessage(content="""{
  "approved": true,
  "critique": "Plan looks complete.",
  "score": 8,
  "criteria_scores": {
    "completeness": 8,
    "compatibility": 8,
    "feasibility": 8,
    "docker": 8,
    "file_coverage": 8
  },
  "checklist_failures": [],
  "root_cause_analysis": "",
  "agent_responsible": "Detail Planner Agent"
}""")

    state: AgentState = {
        "session_id": "test-abap-session-missing-folders",
        "status": "judge",
        "chat_mode": "code",
        "messages": [HumanMessage(content="Build a SAP ABAP ERP program.")],
        # Only has packages/ and docs/ files, missing dictionary/, classes/, reports/, etc.
        "plan": '{"tech_stack": {"language": "abap", "frontend": "none", "backend": "abap"}, "files": ["docs/architecture.md", "packages/zcore/zcl_test.clas.abap"], "steps": []}',
        "environment_info": "Python3 and Node.js pre-installed.",
        "research_context": "",
        "judge_attempts": 0,
        "llm_profile": {
            "provider": "ollama",
            "model": "llama3.1:8b"
        }
    }

    with patch("langchain_core.runnables.base.RunnableSequence.ainvoke", new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_response
        
        result = await judge_node(state)
        
        # Verify that it is rejected because of missing folders
        assert result.get("plan_approved") is False
        assert "ABAP Plan is incomplete. The plan MUST contain files in all 16-stage/designated folders. Missing folders:" in result.get("judge_feedback", "")
        assert result.get("status") == "plan"
