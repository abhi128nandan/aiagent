# Change: Whole-Request Context Budgeting + Interactive Terminal Overhaul

**Date:** 2026-06-11
**Type:** Bug-Fix Sprint + Feature
**Status:** Complete (59 backend tests passing, frontend tsc clean)

## Summary
Three workstreams in one session:
1. **Context budgeting** — every LLM request (system + plan + workspace + error + research + messages) is now fitted under the model's context limit via `ContextManager.fit_request()`. Previously only the message history was budgeted; the other components were sent untrimmed, blowing past Groq free-tier's 12k TPM limit.
2. **Interactive terminal** — the user could never answer CLI prompts (dead code path, nonexistent tab, read-only terminal). Now: amber question banner with **clickable option buttons** for select menus / text input for write prompts, plus an always-visible stdin row in the Agent Terminal.
3. **Auto-responder correctness** — it was cancelling create-vite's scaffold by sending `y\n` to an arrow-key menu. Now parses menu options (clack box prefixes, stale redraw frames), navigates with arrow keys, sends Enter as `\r` (raw-mode TUIs ignore `\n`), and escalates to the user after 3 identical ineffective answers.

## Files Changed

| File | Change |
|------|--------|
| `backend/agent/context_manager.py` | Added `fit_request()` (whole-request budgeter), `truncate_text_tokens()` (head/tail/middle), message compaction (strips old `<write>` bodies — file contents live in workspace context), response buffer 2k→3k, non-string coercion |
| `backend/agent/nodes.py` | `plan_bootstrap_node`, `plan_detail_node`, `implement_node` now build prompts from `fit_request()` output; raw error capped to tail; `error_history or None` clobber fixed |
| `backend/agent/graph.py` | Fixed dead fatal-error routing (checked dict on a string; referenced nonexistent categories) — now reads structured category/severity from `error_history` |
| `backend/agent/judge_node.py`, `research_node.py` | Fixed `AttributeError` crash when `llm_profile` is an LLMProfile object (pydantic has no `.get()`) — isinstance check now first |
| `backend/agent/state_manager.py` | Added 4 missing token-metric fields to initial state; `merge_state_updates` treats `None` as "no change" for list keys |
| `backend/services/conversation_service.py` | `add_event` upserts the conversation row first — FK violations no longer silently drop session events |
| `backend/runtime.py` | Menu-aware auto-responder (`_parse_menu_options` last-frame parsing, `_detect_menu_answer`, `_menu_answer_for_index`); ALL answers use `\r` not `\n`; auto-answer loop guard; richer `interactive_waiting` broadcast (prompt/options/input_type/command); input echo confirmation; `_init_shell` timeout tolerance; exit-code fallback logged; queue cleanup in `cleanup()` |
| `frontend/src/components/Terminal.tsx` | `InteractiveInputBar` (amber banner: option buttons for select menus, text input otherwise) + `AgentStdinRow` (persistent stdin to running command) |
| `frontend/src/store/agentStore.ts` | Interactive state carries prompt/command/options; `sendInteractiveInput` returns success + optimistic banner clear |
| `frontend/src/hooks/useAgentStream.ts` | Stale-WebSocket handler guards (`ws.current !== socket`), handlers detached before close, parse errors logged to correct session, menu-aware chat notifications |
| `backend/tests/` | `test_cli_prompt_detection.py` (9 tests incl. redrawn-frames + no-`\n` guard), rewrote `test_plan_node_token_management.py` for `plan_bootstrap_node`, updated `test_context_resolving.py` (12k cap is intentional) |

## Key Bug Chain (interactive terminal)
1. Chat directed user to a tab that didn't exist; the real tab was read-only; `sendInteractiveInput` had zero callers → answers could never be sent.
2. Auto-responder sent `y\n` to create-vite's radio menu → Enter selected "Cancel operation" → agent cancelled its own scaffold.
3. Real clack output prefixes options with `│` box chars → parser missed them.
4. Enter sent as `\n` is ignored by raw-mode TUIs → infinite auto-answer loop (`[auto-answer: ⏎]` × 6).
5. TUI repaints stack stale menu frames in the buffer → wrong cursor position → wrong arrow counts.

## Verification
- Backend: 59 tests pass (`pytest tests/ --ignore=tests/diagnostic_groq_and_agent.py`)
- Frontend: `tsc -p tsconfig.app.json --noEmit` clean
- Stress test: 22k-token session request fitted to 7,482/12,000 tokens with error tail + decision history preserved
