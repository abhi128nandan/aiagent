import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path to import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.nodes import validate_node
from agent.schema import CmdRunAction
from agent.state import AgentState

@pytest.mark.anyio
async def test_validate_node_content_integrity_fails_on_boilerplate():
    # Setup mock runtime
    runtime = MagicMock()
    runtime.execute = AsyncMock()
    runtime.health_check = AsyncMock()
    
    # Mock runtime.health_check to return unhealthy
    runtime.health_check.return_value = {"healthy": False, "status_code": 0}
    
    def side_effect(action):
        if isinstance(action, CmdRunAction):
            cmd = action.command
            if "package.json" in cmd:
                return {"exit_code": 0, "output": ""}
            elif "npx tsc" in cmd:
                return {"exit_code": 0, "output": ""}
            elif "grep -q '\"test\"'" in cmd:
                return {"exit_code": 1, "output": ""}
            elif "test -f /workspace/src/App.jsx" in cmd:
                return {"exit_code": 0, "output": ""}
            elif "test -f /workspace/src/App.tsx" in cmd:
                return {"exit_code": 1, "output": ""}
            elif "test -f /workspace/src/main.jsx" in cmd:
                return {"exit_code": 1, "output": ""}
            elif "test -f /workspace/src/index.css" in cmd:
                return {"exit_code": 1, "output": ""}
            elif "cat /workspace/src/App.jsx" in cmd:
                # Unmodified Vite boilerplate content
                return {"exit_code": 0, "output": """
import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <h1>Vite + React</h1>
      <p>Click on the Vite and React logos to learn more</p>
    </>
  )
}
export default App
"""}
        return {"exit_code": 1, "output": ""}
        
    runtime.execute.side_effect = side_effect
    
    # State with planning steps
    state: AgentState = {
        'session_id': 'session-integrity-123',
        'status': 'validate',
        'plan': '{"steps": [{"file": "src/App.jsx", "action": "modify"}]}',
        'modified_files': ['src/App.jsx']
    }
    
    with patch('agent.nodes.DockerRuntime.get', return_value=runtime):
        new_state = await validate_node(state)
        
    # Check that validation failed due to boilerplate App.jsx
    validation_results = new_state.get('validation_results', [])
    assert len(validation_results) > 0
    results = validation_results[0]
    
    # Compile passed, but integrity failed
    assert results['level1_compilation']['passed'] is True
    assert results['level1_5_integrity']['passed'] is False
    assert results['level1_5_integrity']['details'][0]['passed'] is False
    assert "boilerplate" in results['level1_5_integrity']['details'][0]['reason'].lower()
    
    # The score should reflect the integrity check failure
    # (score = 20 for compilation, but NO 15 for integrity) -> score = 20
    assert results['validation_score'] == 20


@pytest.mark.anyio
async def test_validate_node_content_integrity_fails_on_todo_comments():
    runtime = MagicMock()
    runtime.execute = AsyncMock()
    runtime.health_check = AsyncMock()
    runtime.health_check.return_value = {"healthy": False, "status_code": 0}
    
    def side_effect(action):
        if isinstance(action, CmdRunAction):
            cmd = action.command
            if "package.json" in cmd:
                return {"exit_code": 1, "output": ""}
            elif "python3 -m py_compile" in cmd:
                return {"exit_code": 0, "output": ""}
            elif "pytest --version" in cmd:
                return {"exit_code": 1, "output": ""}
            elif "test -f /workspace/main.py" in cmd:
                return {"exit_code": 0, "output": ""}
            elif "cat /workspace/main.py" in cmd:
                return {"exit_code": 0, "output": "# TODO: implement actual feature logic here\ndef main():\n    pass"}
        return {"exit_code": 1, "output": ""}
        
    runtime.execute.side_effect = side_effect
    
    state: AgentState = {
        'session_id': 'session-integrity-todo',
        'status': 'validate',
        'plan': '{"steps": [{"file": "main.py", "action": "modify"}]}',
        'modified_files': ['main.py']
    }
    
    with patch('agent.nodes.DockerRuntime.get', return_value=runtime):
        new_state = await validate_node(state)
        
    validation_results = new_state.get('validation_results', [])
    assert len(validation_results) > 0
    results = validation_results[0]
    
    assert results['level1_5_integrity']['passed'] is False
    assert results['level1_5_integrity']['details'][0]['passed'] is False
    assert "placeholder/todo" in results['level1_5_integrity']['details'][0]['reason'].lower()


# ── Pre-write content alignment tests (StaticValidator) ──────────────


def test_pre_write_blocks_boilerplate_content():
    """Verify that validate_content_alignment catches Vite boilerplate at write time."""
    from agent.static_validator import StaticValidator
    
    validator = StaticValidator()
    
    vite_boilerplate = """
import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <h1>Vite + React</h1>
      <p>Click on the Vite and React logos to learn more</p>
    </>
  )
}
export default App
"""
    result = validator.validate_content_alignment('src/App.jsx', vite_boilerplate)
    assert result.passed is False
    assert any("boilerplate" in e.lower() for e in result.errors)


def test_pre_write_blocks_todo_comments():
    """Verify that validate_content_alignment catches TODO comments at write time."""
    from agent.static_validator import StaticValidator
    
    validator = StaticValidator()
    
    code_with_todo = """
# TODO: implement actual feature logic here
def main():
    pass
"""
    result = validator.validate_content_alignment('main.py', code_with_todo)
    assert result.passed is False
    assert any("placeholder" in e.lower() or "todo" in e.lower() for e in result.errors)


def test_pre_write_allows_clean_code():
    """Verify that validate_content_alignment passes valid custom code."""
    from agent.static_validator import StaticValidator
    
    validator = StaticValidator()
    
    clean_code = """
import { useState } from 'react'

function TodoApp() {
  const [tasks, setTasks] = useState([])
  const [input, setInput] = useState('')

  const addTask = () => {
    if (input.trim()) {
      setTasks([...tasks, { text: input, done: false }])
      setInput('')
    }
  }

  return (
    <div className="app">
      <h1>My Todo App</h1>
      <input value={input} onChange={(e) => setInput(e.target.value)} />
      <button onClick={addTask}>Add Task</button>
    </div>
  )
}
export default TodoApp
"""
    result = validator.validate_content_alignment('src/App.jsx', clean_code)
    assert result.passed is True


def test_pre_write_blocks_empty_file():
    """Verify that validate_content_alignment rejects empty files."""
    from agent.static_validator import StaticValidator
    
    validator = StaticValidator()
    
    result = validator.validate_content_alignment('src/App.jsx', '')
    assert result.passed is False
    assert any("empty" in e.lower() for e in result.errors)
