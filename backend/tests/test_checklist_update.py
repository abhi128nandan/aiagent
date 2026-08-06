import sys
import os
import pytest
import tarfile
from unittest.mock import AsyncMock, MagicMock

# Add parent directory to path to import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.nodes import update_tasks_todo

@pytest.mark.anyio
async def test_update_tasks_todo_create_and_modify():
    # Setup mock runtime and container
    runtime = MagicMock()
    mock_container = MagicMock()
    runtime.container = mock_container
    
    mock_exec_res = MagicMock()
    mock_exec_res.exit_code = 0
    mock_container.exec_run.return_value = mock_exec_res
    
    # State with plan having one create and one modify step
    state = {
        'plan': '{"project": "test-project", "description": "test-desc", "steps": [{"file": "src/App.jsx", "action": "modify", "description": "Modify App"}, {"file": "src/NewFile.jsx", "action": "create", "description": "Create NewFile"}]}',
        'modified_files': []
    }
    
    # Call update_tasks_todo
    await update_tasks_todo(runtime, "session-123", state)
    
    # Check that put_archive was called to write tasks_todo.md
    assert mock_container.put_archive.call_count >= 1
    args, kwargs = mock_container.put_archive.call_args
    assert args[0] == '/workspace'
    tar_stream = args[1]
    
    tar_stream.seek(0)
    with tarfile.open(fileobj=tar_stream, mode='r') as tar:
        file_member = tar.getmember("tasks_todo.md")
        content = tar.extractfile(file_member).read().decode('utf-8')
        
    # Since modified_files is empty, the "modify" step (src/App.jsx) should be [ ]
    # The "create" step (src/NewFile.jsx) should be [x] because file exists (exists=True)
    assert "- [ ] **MODIFY** `src/App.jsx`" in content
    assert "- [x] **CREATE** `src/NewFile.jsx`" in content
    
    # Now simulate modified_files contains src/App.jsx
    state['modified_files'] = ['src/App.jsx']
    mock_container.reset_mock()
    mock_container.exec_run.return_value = mock_exec_res
    
    await update_tasks_todo(runtime, "session-123", state)
    
    assert mock_container.put_archive.call_count >= 1
    args, kwargs = mock_container.put_archive.call_args
    tar_stream = args[1]
    tar_stream.seek(0)
    with tarfile.open(fileobj=tar_stream, mode='r') as tar:
        file_member = tar.getmember("tasks_todo.md")
        content = tar.extractfile(file_member).read().decode('utf-8')
        
    # Now the "modify" step should be [x]
    assert "- [x] **MODIFY** `src/App.jsx`" in content
    assert "- [x] **CREATE** `src/NewFile.jsx`" in content


@pytest.mark.anyio
async def test_update_tasks_todo_boilerplate_create():
    # Setup mock runtime and container
    runtime = MagicMock()
    mock_container = MagicMock()
    runtime.container = mock_container
    
    mock_exec_res = MagicMock()
    mock_exec_res.exit_code = 0
    mock_container.exec_run.return_value = mock_exec_res
    
    # State with plan having standard boilerplate file under "create" action
    state = {
        'plan': '{"project": "test-project", "description": "test-desc", "steps": [{"file": "src/App.jsx", "action": "create", "description": "Create App"}]}',
        'modified_files': []
    }
    
    # Call update_tasks_todo
    await update_tasks_todo(runtime, "session-123", state)
    
    # Check that put_archive was called
    assert mock_container.put_archive.call_count >= 1
    args, kwargs = mock_container.put_archive.call_args
    tar_stream = args[1]
    tar_stream.seek(0)
    with tarfile.open(fileobj=tar_stream, mode='r') as tar:
        file_member = tar.getmember("tasks_todo.md")
        content = tar.extractfile(file_member).read().decode('utf-8')
        
    # Since it is a boilerplate file and modified_files is empty, it must be [ ] (incomplete)
    # even though action is "create" and file exists.
    assert "- [ ] **CREATE** `src/App.jsx`" in content
    
    # Now add to modified_files
    state['modified_files'] = ['src/App.jsx']
    mock_container.reset_mock()
    mock_container.exec_run.return_value = mock_exec_res
    await update_tasks_todo(runtime, "session-123", state)
    
    assert mock_container.put_archive.call_count >= 1
    args, kwargs = mock_container.put_archive.call_args
    tar_stream = args[1]
    tar_stream.seek(0)
    with tarfile.open(fileobj=tar_stream, mode='r') as tar:
        file_member = tar.getmember("tasks_todo.md")
        content = tar.extractfile(file_member).read().decode('utf-8')
        
    # Now it should be [x]
    assert "- [x] **CREATE** `src/App.jsx`" in content
