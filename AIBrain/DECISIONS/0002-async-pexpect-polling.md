# Decision 0002: Async Pexpect Polling

## Date
2026-06-10

## Status
Accepted

## Context
Need to capture interactive terminal output (including prompts,
partial lines) from Docker containers in real time.

## Decision
Use pexpect with async polling loop in terminal_proxy.py.
Poll for output every 50ms, push to WebSocket on change.

## Consequences
- Handles interactive programs (vim, python REPL, etc.)
- Small polling delay (50ms) acceptable for terminal UX
- Must handle EOF and process exit cleanly
