# Decision 0004: Whole-Request Context Budgeting (fit_request)

**Date:** 2026-06-11
**Status:** Accepted

## Context
The project runs on Groq free tier: `llama-3.3-70b-versatile` has a 128k window but only ~12k tokens/minute — any single request over ~12k fails with 413. The old ContextManager only pruned the **message history**; plan JSON, workspace context, raw error logs, research, and SRS were sent untrimmed on top.

## Decision
1. `MODEL_CONTEXT_LIMITS` deliberately caps llama-3.3-70b at **12_000** (the effective per-request limit, not the true window). Do not "fix" this to 128k.
2. All planning/implementation LLM calls go through `ContextManager.fit_request()`: each prompt component gets a max **share** of the budget (trimmed head/tail/middle as appropriate — error logs keep the tail), unused share flows to message history, and a response buffer is reserved.
3. Before summarizing history, **compact** old `<write>`/`<replace>` bodies out of messages — the current file contents are re-injected via workspace context every turn, so history only needs to record *which* files were touched.

## Consequences
- A request that previously totalled ~22k tokens fits at ~7.5k with no loss of decisions/errors/file inventory.
- New nodes/LLM calls MUST use `fit_request()` rather than passing state fields straight into prompt templates.

## Related
- `[[0003-two-phase-planning]]` — the nodes this applies to
- Memory: Groq 12k context budget (user-level constraint)
