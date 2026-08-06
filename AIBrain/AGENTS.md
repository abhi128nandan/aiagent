# AI AGENT CONTEXT — myaiagent Project

## HOW TO USE THIS FILE
You are an AI assistant working on this codebase.
Read this file completely before taking any action.
This file tells you what exists, what the rules are, and where to look.

## PROJECT SUMMARY
Name: myaiagent (Antigravity AI-powered IDE)
Stack: FastAPI + LangGraph + Groq API + React frontend
Goal: AI coding assistant with Docker sandboxing, bidirectional terminal streaming, ABAP support on SAP BTP

## READ ORDER (always follow this)
1. AGENTS.md          ← you are here
2. CURRENT_STATE.md   ← what is active RIGHT NOW
3. PROJECT_GRAPH.json ← component/file map
4. FEATURES/<name>.md ← only the relevant feature
5. DECISIONS/<id>.md  ← only if architecture question

## FILE MAP
| File/Dir            | Purpose                         | Editable by AI? |
|---------------------|---------------------------------|-----------------|
| AGENTS.md           | Schema + rules (this file)      | NO              |
| CURRENT_STATE.md    | Active sprint, blockers         | YES — rewrite   |
| PROJECT_GRAPH.json  | Source of truth, component map  | YES — update    |
| _pending.md         | Compilation queue               | YES — append    |
| _log.md             | Audit trail                     | YES — append    |
| FEATURES/           | Per-feature docs                | YES — update    |
| DECISIONS/          | Architecture decision records   | NO — append only|
| CHANGES/            | Change history                  | YES — append    |

## HARD RULES
1. Read CURRENT_STATE.md before answering any project question
2. Never invent facts not present in source files
3. Always append a timestamped entry to _log.md after every run
4. DECISIONS/ files are append-only once created — never overwrite
5. If unsure about project state, ask before assuming

## TASK PROTOCOL
Before executing any task:
- State what you understand the goal to be
- State which files you will read and modify
- Ask one clarifying question if anything is ambiguous
- Only proceed after confirmation

## SESSION STARTER PROMPT
Read AGENTS.md fully. Then read CURRENT_STATE.md.
Answer: what is the active feature, what is the current blocker,
and what file should we work on next?
Do not start any task until you have done this.