# Current State
_Last updated: 2026-06-15_

## Active Sprint
Terminal UX Upgrades & Process Control Integration

## Active Feature
Active process indicators, signal controls (SIGINT/SIGKILL), hotkeys, process panel, and LangGraph task control dashboard.

## Status
- [x] Shell PID tracking — tracking shell PID and child processes inside the Docker container via `echo $$` and container inspects.
- [x] Process control buttons & signals — added `Stop` (SIGINT), `Force Kill` (SIGKILL), `Restart` loop, and `Clear` inside `backend/runtime.py` and WS endpoints.
- [x] Advanced stdin input — replaced single-line input with auto-resizing textarea supporting suggestions, command history, and shortcuts (Ctrl+C, Ctrl+Z, Ctrl+L, Ctrl+Shift+C, Esc).
- [x] Sandbox process monitor — polling container processes in background and broadcasting via WebSocket for collapsible side-panel listing.
- [x] Agent task controls — integrated pause breakpoints (`check_paused` utility) in LangGraph nodes; added Pause/Resume/Cancel task controls in frontend dashboard.
- [x] Long-running command detection — UI alerts if a command executes for more than 10s (possible loop) or 60s (stalled warning).
- [x] Safety confirmations — modals to prevent accidental execution of Force Kill or Task Cancellation.
- [x] Context budgeting — `ContextManager.fit_request()` fits request under Groq 12k TPM cap.
- [x] Boilerplate detection & validation — Level 1.5 file content checks to reject unmodified defaults.
- [x] Tests & builds — backend test suite clean; frontend Vite build compile clean.

## Current Blocker
None

## Next Tasks
1. Live-verify: Ask the agent to scaffold a new application and check that the entrypoint `App.jsx` is successfully modified and passes Level 1.5 validation.
2. Live-verify: Test interrupting a running server command using the `Stop` (SIGINT) button in the Active Process Header.
3. Monitor `fit_request_still_over_limit` warnings in logs during live sessions.

## Recent Decisions
- 0001: Shared WebSocket + Zustand store
- 0002: Async pexpect polling strategy
- 0003: Two-phase planning (bootstrap → scaffold → detail plan)
- 0004: Whole-request context budgeting (`fit_request`, Groq 12k cap is intentional)
- 0005: Background process polling and signal execution via Docker API execs

