# Automation Log
<!-- Format: ## [YYYY-MM-DD] job-type -->

## [2026-06-16] pre-built-templates-strategy
- Replaced unreliable LLM-generated CLI scaffolding commands with a deterministic template-copying strategy in `plan_bootstrap_node` and `setup_environment_node`.
- Updated `BOOTSTRAP_PLAN_SCHEMA_INSTRUCTIONS` in `prompts.py` to use a `template_selected` enum instead of `scaffold_command`.
- Updated `setup_environment_node` in `nodes.py` to copy boilerplate folders from `backend/templates/` using `shutil.copytree` and run `npm install` inside the container runtime.
- Updated `VerificationRuleEngine` mapping and created `validate_template_selection` in `verification_rules.py` to enforce the new schema.
- Refactored `test_verification_pipeline.py` and `test_verification_engine.py` unit test mocks to pass with the new validation structure.
- Generated standard `react-vite` and `express` baseline templates inside `backend/templates/`.
- Files changed: agent/prompts.py, agent/nodes.py, agent/verification_rules.py, tests/test_verification_pipeline.py, tests/test_verification_engine.py

## [2026-06-15] terminal-ux-upgrades-and-process-control
- Integrated active process tracking and runtime monitoring in `backend/runtime.py` and frontend Zustand/WebSocket stream routers.
- Added interactive process controls (Stop, Force Kill, Restart, Clear) via system signals (SIGINT, SIGKILL, SIGTSTP).
- Implemented collapsible sandbox process list panel to monitor and control Docker container tasks.
- Overhauled Agent Stdin to support auto-resizing textareas, multi-line commands, autocomplete suggestions, ALT-Up/Down history navigation, and shortcuts.
- Added LangGraph execution node checkpoints for Pause/Resume/Cancel task controls.
- Added visual execution task control dashboard and confirmation modals for dangerous operations.
- Refined process controls: Added pure-Python `/proc` parsing fallback for PID detection, recursive descendant process tree killing (leaf-to-root signal delivery), and direct shell keystroke/control-character signal fallbacks for falsy/missing process PIDs.
- Files changed: backend/runtime.py, backend/routes/agent.py, backend/agent/nodes.py, Terminal.tsx, agentStore.ts, useAgentStream.ts
- Docs created: CHANGES/2026-06-15-terminal-ux-upgrades.md
- Updated: CURRENT_STATE.md, _log.md

## [2026-06-15] boilerplate-remediation-and-validation-integrity
- Added Level 1.5 file content and integrity validation check to `validate_node` to reject empty files and detect unmodified Vite counter templates in `src/App.jsx`/`src/App.tsx`.
- Updated checklist task manager (`update_tasks_todo`) to enforce that standard boilerplate files must be modified in the session to be marked completed, avoiding the issue where pre-existing scaffolded files were marked done immediately.
- Re-distributed the 100-point validation score to assign 15 points to Level 1.5 file integrity.
- Created `test_validation_integrity.py` and added `test_update_tasks_todo_boilerplate_create` to verify both fixes.
- Files changed: nodes.py, prompts.py, react.md, test_checklist_update.py, test_validation_integrity.py
- Docs created: CHANGES/2026-06-15-boilerplate-remediation-and-validation-integrity.md
- Updated: CURRENT_STATE.md, _log.md

## [2026-06-11] context-budgeting-and-interactive-fixes
- Added `ContextManager.fit_request()` — budgets the ENTIRE LLM request (system + plan + workspace + error + research + messages) under the model limit; Groq 12k free-tier cap is intentional
- Added message compaction (strips old `<write>`/`<replace>` bodies from history) + token-aware head/tail/middle truncation
- Wired fit_request into `plan_bootstrap_node`, `plan_detail_node`, `implement_node` (previously pruning was stats-only; components were sent untrimmed)
- Fixed dead fatal-error routing in `graph.py` (string-vs-dict check + nonexistent categories)
- Fixed LLMProfile `.get()` AttributeError crash in `judge_node.py` / `research_node.py`
- Fixed `error_history or None` clobbering accumulated history; merge treats None as "no change" for list keys
- Fixed event-persistence FK violations (`add_event` upserts conversation row)
- Fixed stale WebSocket handlers firing for old sessions on rapid reconnects (frontend)
- Interactive terminal overhaul: amber question banner with clickable option buttons (select menus) / text input (write prompts); persistent stdin row in Agent Terminal; `sendInteractiveInput` was dead code with zero callers before
- Auto-responder: menu-aware (clack `│` box prefixes, stale redraw frames → last-frame parsing), arrow-key navigation, Enter as `\r` not `\n` (raw-mode TUIs), loop guard (3 identical answers → ask user); was cancelling create-vite scaffold via blind `y\n`
- Tests: 59 backend passing (new `test_cli_prompt_detection.py`, rewrote `test_plan_node_token_management.py`, updated `test_context_resolving.py`); frontend tsc clean
- Files changed: context_manager.py, nodes.py, graph.py, judge_node.py, research_node.py, state_manager.py, conversation_service.py, runtime.py, Terminal.tsx, agentStore.ts, useAgentStream.ts
- Docs created: CHANGES/2026-06-11-context-budgeting-and-interactive-fixes.md, DECISIONS/0004-whole-request-context-budgeting.md
- Updated: CURRENT_STATE.md, work_log.xlsx
- Pending decision: research engine replacement (Tavily / Gemini grounding / recipe table — options presented to user)

## [2026-06-10] two-phase-planning
- Implemented two-phase planning architecture (bootstrap → scaffold → detail plan)
- Fixed workspace path mismatch between nodes.py and runtime.py
- Fixed LangChain template variable escape in detail plan prompt
- Fixed workspace path sync by starting interactive shell in `/workspace`
- Added automatic port-freeing (`fuser` / `kill-port`) before starting dev servers
- Added dynamic `tasks_todo.md` checklist creation & update in the workspace
- Files changed: state.py, state_manager.py, prompts.py, nodes.py, graph.py, runtime.py
- Docs created: CHANGES/2026-06-10-two-phase-planning.md, DECISIONS/0003-two-phase-planning.md
- Updated: FEATURES/AgentWorkflow.md, PROJECT_GRAPH.json, CURRENT_STATE.md

## [2026-06-10] vault-init
- Project Memory System initialized
- Files created: AGENTS.md, CURRENT_STATE.md, PROJECT_GRAPH.json, _pending.md, _log.md
- Directories created: FEATURES/, DECISIONS/, CHANGES/
