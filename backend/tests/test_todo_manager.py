"""
Tests for TodoManager — structured plan state persistence.

Verifies:
- Plan sync creates TodoItems with correct statuses
- Completed items survive across re-syncs
- Judge mid-run appends preserve completed items
- Status transitions (pending → in_progress → completed)
- Markdown backward compatibility
- JSON serialization roundtrip
"""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.todo_manager import TodoManager, TodoItem, TodoList, _todo_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the module-level todo cache before each test."""
    _todo_cache.clear()
    yield
    _todo_cache.clear()


SAMPLE_PLAN = json.dumps({
    "project": "test-project",
    "description": "A test project",
    "steps": [
        {"file": "src/App.jsx", "action": "modify", "description": "Update App component"},
        {"file": "src/api.js", "action": "create", "description": "Create API module"},
        {"file": "src/index.css", "action": "modify", "description": "Update styles"},
    ]
})


def test_sync_from_plan_creates_todos():
    """Verify plan steps become TodoItems with pending status."""
    mgr = TodoManager("session-1")
    result = mgr.sync_from_plan(SAMPLE_PLAN)

    assert len(result.items) == 3
    assert result.project == "test-project"
    assert all(item.status == "pending" for item in result.items)
    assert result.items[0].file_path == "src/App.jsx"
    assert result.items[0].action == "modify"
    assert result.items[1].file_path == "src/api.js"
    assert result.items[1].action == "create"


def test_sync_preserves_completed():
    """Re-sync after marking items completed; completed items must survive."""
    mgr = TodoManager("session-2")
    mgr.sync_from_plan(SAMPLE_PLAN)

    # Mark first item as completed
    mgr.mark_file_completed("src/App.jsx")
    assert mgr.todo_list.items[0].status == "completed"

    # Re-sync with same plan (simulates Judge rejection → re-plan)
    mgr.sync_from_plan(SAMPLE_PLAN)

    # The completed item must still be completed
    app_item = next(i for i in mgr.todo_list.items if i.file_path == "src/App.jsx")
    assert app_item.status == "completed"

    # Other items should be pending
    api_item = next(i for i in mgr.todo_list.items if i.file_path == "src/api.js")
    assert api_item.status == "pending"


def test_sync_preserves_completed_not_in_new_plan():
    """Completed items NOT in the new plan should still be preserved."""
    mgr = TodoManager("session-3")
    mgr.sync_from_plan(SAMPLE_PLAN)
    mgr.mark_file_completed("src/App.jsx")

    # New plan without src/App.jsx
    new_plan = json.dumps({
        "project": "test-project",
        "steps": [
            {"file": "src/api.js", "action": "create", "description": "Create API module"},
            {"file": "src/new_file.js", "action": "create", "description": "New file"},
        ]
    })
    mgr.sync_from_plan(new_plan)

    # src/App.jsx should still exist as completed
    paths = [i.file_path for i in mgr.todo_list.items]
    assert "src/App.jsx" in paths
    app_item = next(i for i in mgr.todo_list.items if i.file_path == "src/App.jsx")
    assert app_item.status == "completed"


def test_append_todos_preserves_completed():
    """Judge appends new items; completed items untouched."""
    mgr = TodoManager("session-4")
    mgr.sync_from_plan(SAMPLE_PLAN)
    mgr.mark_file_completed("src/App.jsx")

    appended = mgr.append_todos([
        {"content": "Add error boundary", "file_path": "src/ErrorBoundary.jsx", "action": "create"},
        {"content": "Update existing", "file_path": "src/App.jsx", "action": "modify"},  # Duplicate — skip
    ])

    assert appended == 1  # Only ErrorBoundary added, App.jsx skipped (duplicate)
    assert len(mgr.todo_list.items) == 4

    # Completed item untouched
    app_item = next(i for i in mgr.todo_list.items if i.file_path == "src/App.jsx")
    assert app_item.status == "completed"

    # New item is pending
    err_item = next(i for i in mgr.todo_list.items if i.file_path == "src/ErrorBoundary.jsx")
    assert err_item.status == "pending"


def test_update_status_transitions():
    """pending → in_progress → completed lifecycle."""
    mgr = TodoManager("session-5")
    mgr.sync_from_plan(SAMPLE_PLAN)

    assert mgr.todo_list.items[0].status == "pending"

    mgr.mark_file_in_progress("src/App.jsx")
    assert mgr.todo_list.items[0].status == "in_progress"

    mgr.mark_file_completed("src/App.jsx")
    assert mgr.todo_list.items[0].status == "completed"


def test_update_status_normalized_path():
    """File paths with/without leading slashes should match."""
    mgr = TodoManager("session-6")
    mgr.sync_from_plan(SAMPLE_PLAN)

    # Use leading-slash variant
    found = mgr.mark_file_completed("/src/App.jsx")
    assert found is True
    assert mgr.todo_list.items[0].status == "completed"


def test_update_status_not_found():
    """Updating a non-existent file returns False."""
    mgr = TodoManager("session-7")
    mgr.sync_from_plan(SAMPLE_PLAN)

    found = mgr.mark_file_completed("nonexistent.py")
    assert found is False


def test_to_markdown_backward_compat():
    """Markdown output matches existing update_tasks_todo format."""
    mgr = TodoManager("session-8")
    mgr.sync_from_plan(SAMPLE_PLAN)
    mgr.mark_file_completed("src/App.jsx")
    mgr.mark_file_in_progress("src/api.js")

    md = mgr.to_markdown()

    assert "- [x] **MODIFY** `src/App.jsx`" in md
    assert "- [/] **CREATE** `src/api.js`" in md
    assert "- [ ] **MODIFY** `src/index.css`" in md
    assert "# Project: test-project" in md


def test_sync_invalid_plan():
    """Invalid JSON plan should not crash, returns empty TodoList."""
    mgr = TodoManager("session-9")
    result = mgr.sync_from_plan("not valid json")
    assert len(result.items) == 0


def test_sync_empty_steps():
    """Plan with no steps should produce empty items list."""
    mgr = TodoManager("session-10")
    result = mgr.sync_from_plan(json.dumps({"project": "x", "steps": []}))
    assert len(result.items) == 0


def test_append_empty_content_skipped():
    """Items with empty content should be skipped."""
    mgr = TodoManager("session-11")
    mgr.sync_from_plan(SAMPLE_PLAN)
    appended = mgr.append_todos([{"content": "", "file_path": "x.js"}])
    assert appended == 0


def test_cache_isolation():
    """Different sessions maintain separate todo lists."""
    mgr1 = TodoManager("session-a")
    mgr1.sync_from_plan(SAMPLE_PLAN)
    mgr1.mark_file_completed("src/App.jsx")

    mgr2 = TodoManager("session-b")
    mgr2.sync_from_plan(json.dumps({"project": "other", "steps": [
        {"file": "main.py", "action": "create", "description": "Main"}
    ]}))

    assert len(mgr1.todo_list.items) == 3
    assert len(mgr2.todo_list.items) == 1
    assert mgr1.todo_list.items[0].status == "completed"
    assert mgr2.todo_list.items[0].status == "pending"


def test_serialization_roundtrip():
    """TodoList serializes to JSON and deserializes correctly."""
    mgr = TodoManager("session-12")
    mgr.sync_from_plan(SAMPLE_PLAN)
    mgr.mark_file_completed("src/App.jsx")

    json_str = mgr.todo_list.model_dump_json()
    restored = TodoList.model_validate_json(json_str)

    assert len(restored.items) == 3
    assert restored.project == "test-project"
    assert restored.items[0].status == "completed"
    assert restored.items[0].file_path == "src/App.jsx"
