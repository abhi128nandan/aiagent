import asyncio
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, ANY
from fastapi import WebSocketDisconnect

# Read routes/agent.py and extract process_monitor_loop source code
with open("routes/agent.py", "r") as f:
    content = f.read()

# Match the process_monitor_loop function block
match = re.search(r"    async def process_monitor_loop\(\):.*?(?=    async def ping_loop)", content, re.DOTALL)
if not match:
    raise RuntimeError("Could not find process_monitor_loop in routes/agent.py")

# Strip the leading indentation (4 spaces)
func_code = "\n".join(line[4:] if line.startswith("    ") else line for line in match.group(0).split("\n"))

# Compile the function code so it can be executed in a namespace
local_vars = {}
# Provide globals and execute the function definition to populate local_vars
exec(func_code, {
    "asyncio": asyncio,
    "WebSocketDisconnect": WebSocketDisconnect,
    "RuntimeError": RuntimeError,
}, local_vars)
process_monitor_loop = local_vars["process_monitor_loop"]


@pytest.mark.anyio
async def test_process_monitor_loop_breaks_on_runtime_error():
    # Setup mock variables that the nested function references from enclosing scope
    ws = AsyncMock()
    ws.send_json.side_effect = RuntimeError("Unexpected ASGI message 'websocket.send'...")
    
    session_id = "test_session"
    
    # Mock logger
    logger = MagicMock()
    
    # Mock DockerRuntime
    mock_rt = AsyncMock()
    mock_rt.get_active_processes.return_value = []
    mock_rt.get_foreground_process.return_value = None
    
    # Mock DockerRuntime.get class method
    mock_docker_runtime_cls = MagicMock()
    mock_docker_runtime_cls.get.return_value = mock_rt
    
    # Create the enclosing environment (closure simulation)
    # Since process_monitor_loop references session_id, ws, logger from outer scope,
    # we inject them into the function's globals/closure.
    # In python, we can execute the function by setting its __globals__ or using a wrapper
    # that defines these variables. Since we compiled it, the globals dict used during
    # exec is function's __globals__.
    
    globals_dict = {
        "asyncio": asyncio,
        "WebSocketDisconnect": WebSocketDisconnect,
        "RuntimeError": RuntimeError,
        "ws": ws,
        "session_id": session_id,
        "logger": logger,
    }
    
    # Re-exec with the injected globals so the function resolves them
    exec(func_code, globals_dict, local_vars)
    process_monitor_loop = local_vars["process_monitor_loop"]
    
    # Mock the import of DockerRuntime inside the function
    # The function does: from runtime import DockerRuntime
    # We can patch sys.modules or override runtime in the function's globals
    import sys
    sys.modules["runtime"] = MagicMock()
    sys.modules["runtime"].DockerRuntime = mock_docker_runtime_cls
    
    # Run the loop. To prevent it from sleeping forever or running too long,
    # we patch asyncio.sleep to run instantly or raise cancellation after 1 tick.
    async def mock_sleep(seconds):
        pass
    
    globals_dict["asyncio"].sleep = mock_sleep
    
    # Run the function in a task and set a timeout to be safe
    task = asyncio.create_task(process_monitor_loop())
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("process_monitor_loop did not exit and timed out!")
        
    # The loop should have exited/broken
    assert task.done()
    ws.send_json.assert_called_once()
    logger.debug.assert_called_with("process_monitor_send_failed", session_id=session_id, error=ANY)


@pytest.mark.anyio
async def test_process_monitor_loop_breaks_on_websocket_disconnect():
    # Setup mock variables
    ws = AsyncMock()
    ws.send_json.side_effect = WebSocketDisconnect()
    
    session_id = "test_session"
    logger = MagicMock()
    
    mock_rt = AsyncMock()
    mock_rt.get_active_processes.return_value = []
    mock_rt.get_foreground_process.return_value = None
    
    mock_docker_runtime_cls = MagicMock()
    mock_docker_runtime_cls.get.return_value = mock_rt
    
    globals_dict = {
        "asyncio": asyncio,
        "WebSocketDisconnect": WebSocketDisconnect,
        "RuntimeError": RuntimeError,
        "ws": ws,
        "session_id": session_id,
        "logger": logger,
    }
    
    exec(func_code, globals_dict, local_vars)
    process_monitor_loop = local_vars["process_monitor_loop"]
    
    import sys
    sys.modules["runtime"] = MagicMock()
    sys.modules["runtime"].DockerRuntime = mock_docker_runtime_cls
    
    async def mock_sleep(seconds):
        pass
    globals_dict["asyncio"].sleep = mock_sleep
    
    task = asyncio.create_task(process_monitor_loop())
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("process_monitor_loop did not exit and timed out!")
        
    assert task.done()
    ws.send_json.assert_called_once()
    logger.debug.assert_called_with("process_monitor_send_failed", session_id=session_id, error=ANY)


@pytest.mark.anyio
async def test_process_monitor_loop_breaks_on_generic_websocket_send_error():
    # Setup mock variables where send_json raises a generic Exception but with a websocket-related string
    ws = AsyncMock()
    ws.send_json.side_effect = Exception("Cannot call \"send\" once a close message has been sent.")
    
    session_id = "test_session"
    logger = MagicMock()
    
    mock_rt = AsyncMock()
    mock_rt.get_active_processes.return_value = []
    mock_rt.get_foreground_process.return_value = None
    
    mock_docker_runtime_cls = MagicMock()
    mock_docker_runtime_cls.get.return_value = mock_rt
    
    globals_dict = {
        "asyncio": asyncio,
        "WebSocketDisconnect": WebSocketDisconnect,
        "RuntimeError": RuntimeError,
        "ws": ws,
        "session_id": session_id,
        "logger": logger,
    }
    
    exec(func_code, globals_dict, local_vars)
    process_monitor_loop = local_vars["process_monitor_loop"]
    
    import sys
    sys.modules["runtime"] = MagicMock()
    sys.modules["runtime"].DockerRuntime = mock_docker_runtime_cls
    
    async def mock_sleep(seconds):
        pass
    globals_dict["asyncio"].sleep = mock_sleep
    
    task = asyncio.create_task(process_monitor_loop())
    try:
        await asyncio.wait_for(task, timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("process_monitor_loop did not exit and timed out!")
        
    assert task.done()
    ws.send_json.assert_called_once()
    logger.debug.assert_called_with("process_monitor_error", session_id=session_id, error=ANY)
