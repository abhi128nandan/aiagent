# Change Record: Terminal UX Upgrades and Process Control

## Context & Objectives
The Agent Terminal input experience has been overhauled to behave like a real developer-grade terminal interface.
Previously, when an agent command was running, the UI felt stuck, users could not easily interrupt or suspend running processes (using Ctrl+C, Ctrl+Z), and there were no process-level controls (SIGINT, SIGKILL, Restart, Clear). Additionally, monitoring sandbox processes and controlling LangGraph task execution was not possible.

## Key Accomplishments
1. **Shell PID Tracking & Interactive Run Loop**:
   - Modified `backend/runtime.py` to fetch and persist the sandbox shell PID (`self.shell_pid`).
   - Implemented `get_active_processes`, `get_foreground_process`, and `kill_process` in `DockerRuntime`.
   - Re-structured `_execute_cmd_interactive` to wrap command execution in a loop that listens for restart signals, automatically broadcasts `process_start`/`process_end`/`foreground_pid` event payloads, and supports clean restarts.
2. **WebSocket Upgrades & Monitoring Loop**:
   - Updated `backend/routes/agent.py` to handle inbound WebSocket control frames: `kill_process`, `restart_command`, `pause_agent`, `resume_agent`, and `cancel_agent`.
   - Created `process_monitor_loop` running as a background task that polls Docker container processes every 2 seconds, broadcasting them via WebSocket.
   - Wrapped Graph event streaming in a cancellable task to allow graceful user cancellations.
3. **Agent Graph Pausing Breaks**:
   - Added `check_paused` utility to `backend/agent/nodes.py`.
   - Integrated `check_paused` at the start of all major node functions (`plan_bootstrap_node`, `setup_environment_node`, `plan_detail_node`, `implement_node`, `execute_node`, `validate_node`).
4. **Zustand Store Extensions**:
   - Added store states for processes, foreground processes, current command, and agent task status.
   - Wired in actions to trigger process signals, restart, pause, resume, and cancel agent executions.
5. **Advanced Terminal Component Refactoring (`Terminal.tsx`)**:
   - Implemented **Active Process Control Header** showing status, command, runtime timer, warning badges (10s/60s long running commands), and buttons for `Stop`, `Force Kill`, `Restart`, and `Clear`.
   - Created **Agent Task Control Dashboard** supporting visual progress nodes and user actions (`Pause`/`Resume`/`Cancel`).
   - Added **Collapsible Sandbox Processes Panel** to display sandbox processes and allow targeting individual PIDs.
   - Upgraded input field to an auto-resizing `textarea` with inline/history suggestion auto-completion, ALT-Up/Down history, and global keyboard shortcuts (Ctrl+C, Ctrl+Z, Ctrl+L, Ctrl+Shift+C, Esc).
   - Handled confirmation modals before dangerous operations (Force Kill, Cancel Task).

## Subsequent Enhancements & Refinements
1. **Pure-Python `/proc` Parser Fallback**:
   - Added a secondary `/proc` parsing fallback in `get_active_processes` in `backend/runtime.py`. If the `ps` command is not present or fails inside the container sandbox, a Python script executes to read `/proc` directly and reconstruct process structures.
2. **Recursive Descendant Process Tree Killing**:
   - Updated `kill_process` in `backend/runtime.py` to recursively traverse and resolve all descendants of a target PID. Deliver signals leaf-first (deepest child to parent) to avoid zombie processes.
3. **Control Signal Fallbacks (Falsy/Missing PIDs)**:
   - Updated `kill_process` and WebSocket handlers in `backend/routes/agent.py` to support missing/unknown PIDs.
   - If the PID is falsy/missing, `Stop`/`Ctrl+C` sends `\x03` (SIGINT equivalent) directly to the active shell, `Ctrl+Z` sends `\x1a` (SIGTSTP equivalent), and `Force Kill` closes/terminates the shell process itself.
4. **Refined Long Running Warning Badges**:
   - Replaced the misleading `Possible loop` message for 10s runs with cleaner `RUNNING > 15s` (subtle gray) and `LONG RUNNING > 60s` (amber) status pills in `Terminal.tsx` to match real-world terminal behaviors.

## Files Modified
- `backend/runtime.py`
- `backend/routes/agent.py`
- `backend/agent/nodes.py`
- `frontend/src/store/agentStore.ts`
- `frontend/src/hooks/useAgentStream.ts`
- `frontend/src/components/Terminal.tsx`
