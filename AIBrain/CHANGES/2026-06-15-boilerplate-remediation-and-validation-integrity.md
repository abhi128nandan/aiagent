# Change: Boilerplate Remediation and Validation Integrity Checks

**Date:** 2026-06-15
**Type:** Bug-Fix + Reliability Sprint
**Status:** Complete (62 backend tests passing)

## Summary
Two core reliability improvements:
1. **Level 1.5 File Content & Integrity Checks** — Added a new file content verification step to the validation node (`validate_node`). It checks planned files and entrypoints (like `src/App.jsx`) for existence, non-emptiness, and the presence of unmodified default Vite counter boilerplate code (e.g. `useState(0)` counter coupled with `<h1>Vite + React</h1>`). If boilerplate is found, validation fails and routes back to the implementation stage with a descriptive error.
2. **Boilerplate Task Checklist Safeguard** — Fixed a bug where standard scaffolded boilerplate files (like `src/App.jsx`) were instantly marked complete (`[x]`) in the task checklist before the agent even ran because the file physically existed. They are now checked against `modified_files` in the current session instead of file existence.

## Files Changed

| File | Change |
|------|--------|
| `backend/agent/nodes.py` | 1. Modified `update_tasks_todo` checklist logic to verify `fpath in modified_files` for both `modify` and standard boilerplate files with `create` actions.<br>2. Implemented Level 1.5 Integrity Checks in `validate_node` to parse planned files/entrypoints, verify existence, check non-emptiness, and detect unmodified Vite boilerplate.<br>3. Adjusted the 100-point validation scoring allocation (Level 1: 20, Level 1.5: 15, Level 2: 25, Level 3: 15, Level 4: 15).<br>4. Updated logging metadata to log `integrity` pass/fail. |
| `backend/agent/prompts.py` | Added planning rule 7 forcing the planner to schedule modifications to default scaffold entrypoints. |
| `backend/agent/microagents/react.md` | Appended strict coding rules directing the agent to overwrite Vite boilerplate. |
| `backend/tests/test_checklist_update.py` | Added `test_update_tasks_todo_boilerplate_create` to verify that standard boilerplate files with `create` actions are kept incomplete until modified in the session. |
| `backend/tests/test_validation_integrity.py` | Created integration test validating that unmodified boilerplate in `src/App.jsx` fails Level 1.5 and correctly docks the validation score. |

## Verification
- Backend: All 62 tests pass (`pytest tests/`)
