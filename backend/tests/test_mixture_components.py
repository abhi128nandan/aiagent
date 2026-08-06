import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.command_validator import CommandValidator
from agent.file_history import FileHistoryManager


# ── Test Command Validator ───────────────────────────────────────────

@pytest.mark.anyio
async def test_validator_rm():
    validator = CommandValidator()
    
    # rm without -f
    res = await validator.validate("rm temp.txt")
    assert res.modified is True
    assert res.command == "rm -f temp.txt"
    assert "Added -f flag" in res.warning

    # rm with -f already
    res = await validator.validate("rm -f temp.txt")
    assert res.modified is False
    assert res.command == "rm -f temp.txt"


@pytest.mark.anyio
async def test_validator_cd():
    validator = CommandValidator()
    
    # Mock runtime to simulate folder not existing
    runtime = AsyncMock()
    runtime.execute.return_value = {"exit_code": 1}
    
    res = await validator.validate("cd src/components", runtime)
    assert res.modified is True
    assert res.command == "mkdir -p src/components && cd src/components"


@pytest.mark.anyio
async def test_validator_lsof():
    validator = CommandValidator()
    
    res = await validator.validate("lsof -ti:8080 | xargs kill -9")
    assert res.modified is True
    assert res.command == "fuser -k 8080/tcp 2>/dev/null; true"


@pytest.mark.anyio
async def test_validator_pip():
    validator = CommandValidator()
    
    res = await validator.validate("pip install requests")
    assert res.modified is True
    assert res.command == "pip install --break-system-packages requests"


# ── Test File History Manager ────────────────────────────────────────

@pytest.mark.anyio
async def test_file_history_save_snapshot():
    history = FileHistoryManager()
    
    runtime = AsyncMock()
    runtime.execute.return_value = {"exit_code": 0}
    
    # Save a snapshot
    success = await history.save_snapshot(runtime, "src/index.js", "console.log('hello');")
    assert success is True
    
    # Ensure snapshot path contains the file path and history directory
    calls = runtime.execute.call_args_list
    assert len(calls) == 2
    
    # First call: mkdir
    assert "mkdir -p" in calls[0][0][0].command
    assert ".history/src/index.js" in calls[0][0][0].command
    
    # Second call: write snapshot
    assert calls[1][0][0].path.startswith(".history/src/index.js/")
    assert calls[1][0][0].content == "console.log('hello');"


# ── Test Event Buffer Persistence ────────────────────────────────────

@pytest.mark.anyio
async def test_event_buffer_persistence(monkeypatch):
    from routes.agent import _EventBuffer
    
    # Mock ConversationService to avoid hitting actual postgres during simple tests
    mock_service_instance = MagicMock()
    mock_service_instance.get_events.return_value = [
        {"type": "chat", "content": "hello", "seq": 1},
        {"type": "chat", "content": "world", "seq": 2}
    ]
    mock_service_instance.add_event.return_value = None
    
    class MockConversationService:
        def __new__(cls, *args, **kwargs):
            return mock_service_instance

    monkeypatch.setattr("services.conversation_service.ConversationService", MockConversationService)

    event_buffer = _EventBuffer(max_size=10)
    
    # Test lazy loading
    events = await event_buffer.replay_after("dummy-session-uuid", 0)
    assert len(events) == 2
    assert events[0]["content"] == "hello"
    assert events[1]["content"] == "world"
    
    # Verify seq tracking restored
    assert event_buffer._seq["dummy-session-uuid"] == 2
    
    # Test adding an event
    new_seq = await event_buffer.add("dummy-session-uuid", {"type": "chat", "content": "next"})
    assert new_seq == 3
    assert mock_service_instance.add_event.call_count == 1

