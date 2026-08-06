# Decision 0003: Two-Phase Planning (Bootstrap → Detail)

**Date:** 2026-06-10
**Status:** Accepted
**Deciders:** Developer + AI Agent

## Context
When the user requests "create a React app with Vite", the Planner generates file modification steps _before_ the scaffold command runs. This causes:
- Guessed file paths (e.g., `src/App.js` vs actual `src/App.jsx`)
- `<replace>` instructions targeting non-existent files
- Judge evaluating against an empty workspace
- Coder improvising when paths don't match

## Decision
Split planning into two phases:
1. **Bootstrap Phase** — generates tech_stack, scaffold_command, environment config (no file steps)
2. **Detail Phase** — runs _after_ scaffolding, re-indexes workspace, generates exact file-level steps

## Consequences
### Positive
- Detail Planner sees actual scaffolded files (exact paths, real contents)
- Judge evaluates against a real workspace
- Coder receives precise `<replace>` targets
- Scaffold execution is deterministic (not left to LLM multi-step reasoning)

### Negative
- One additional LLM call (detail planning)
- Slightly longer total pipeline time
- Additional state fields (`planning_phase`, `scaffold_completed`)

## Alternatives Considered
1. **Judge-driven re-plan** — Let the Judge reject blind plans until they match. Rejected because it wastes LLM calls without giving the Planner workspace context.
2. **Single plan with deferred steps** — Keep one plan node but defer `steps[]` generation. Rejected because the Planner needs workspace context to generate good steps, which requires scaffolding first.
