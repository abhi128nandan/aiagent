# Change: Two-Phase Planning Architecture

**Date:** 2026-06-10
**Type:** Architecture Refactor
**Status:** Complete

## Summary
Split the agent's single planning phase into a two-phase pipeline:
**Bootstrap Plan → Scaffold → Detail Plan → Judge → Implement**

Previously, the Planner generated file-level steps _before_ scaffolding ran, causing path mismatches and blind code generation. Now the Detail Planner sees the _actual_ scaffolded files on disk.

## Files Changed

| File | Change |
|------|--------|
| `backend/agent/state.py` | Added `planning_phase`, `scaffold_completed` fields |
| `backend/agent/state_manager.py` | Added defaults for new fields |
| `backend/agent/prompts.py` | Split into `plan_bootstrap_prompt` + `plan_detail_prompt`; simplified `implement_prompt` |
| `backend/agent/nodes.py` | Renamed `plan_node` → `plan_bootstrap_node`; added `plan_detail_node`; moved scaffold execution to `setup_environment_node`; added `update_tasks_todo` helper to initialize & update `tasks_todo.md`; updated `sanitize_command` to auto-free ports |
| `backend/agent/graph.py` | Rewired: `plan_bootstrap → research → setup_environment → plan_detail → judge → implement`; judge rejection routes to `plan_detail` |
| `backend/runtime.py` | Updated `_init_shell` to execute `cd /workspace` on shell startup to align docker shell directory with host workspaces directory |

## Bug Fixes (same session)

### 1. Workspace Path Mismatch
- `nodes.py` computed workspace as `backend/workspaces/{session}` but Docker mounts to `myaiagent/workspaces/{session}`
- **Fix:** Changed `".."` to `"..", ".."` in all 3 path computations in `nodes.py`
- **Impact:** `WorkspaceIndexer` was _always_ reading an empty directory — Coder LLM never saw file contents

### 2. LangChain Template Variable Escape
- `DETAIL_PLAN_SCHEMA_INSTRUCTIONS` had `{project_name}`, `{tech_stack_json}` as JSON examples
- LangChain parsed them as template variables → `KeyError` crash
- **Fix:** Replaced with concrete example values

### 3. Workspace Shell Working Directory (Sync Path Mismatch)
- Interactive pexpect shell was spawned via `docker exec` which defaults to `/root` rather than `/workspace`. This caused the scaffold command (like `create-vite`) to generate the template inside the container's `/root` directory, meaning files never synced to the host workspace volume indexer.
- **Fix:** Appended `cd /workspace` commands to persistent shell initialization (`_init_shell()` in `runtime.py`).
- **Impact:** Scaffolded files sync immediately to host workspaces and are fully visible to the `WorkspaceIndexer` and Detail Planner.

### 4. Container Port Collisions
- Starting background dev servers (e.g. `npm run dev`) sometimes fails due to stale processes occupying ports (like `3000`, `5173`, `8000`).
- **Fix:** Prepend port-killing commands (`fuser -k PORT/tcp` with fallback to `npx -y kill-port`) inside `sanitize_command` in `nodes.py` before executing server commands.
- **Impact:** Automatic port cleanup prevents "port in use" conflicts.

### 5. Dynamic User-Facing Tasks Checklist (`tasks_todo.md`)
- User needed visibility into the scheduled implementation plan tasks and progress in real-time.
- **Fix:** Created `update_tasks_todo` utility in `nodes.py` that writes a `tasks_todo.md` checklist file to `/workspace` based on the active JSON plan. As steps execute, files are detected and checklist progress is updated automatically.
- **Impact:** User can view current tasks and their status directly in the workspace explorer files.

## New Graph Flow
```
plan_bootstrap → research → setup_environment (runs scaffold)
             → plan_detail (re-indexes workspace, generates file steps)
             → judge → implement → execute → validate → END
```

## Decision Rationale
See: `AIBrain/DECISIONS/0003-two-phase-planning.md`
