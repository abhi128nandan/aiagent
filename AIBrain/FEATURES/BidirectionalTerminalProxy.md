# Feature: Bidirectional Interactive Terminal Streaming

## Status
in-progress

## Goal
Real-time stdin/stdout streaming between frontend terminal UI and
backend Docker sandbox over WebSocket.

## Components
- backend/terminal_proxy.py — async pexpect polling
- frontend/src/components/Terminal.jsx — xterm.js or equivalent
- Zustand store — shared WebSocket state

## Decisions Applied
- 0001: Shared WebSocket + Zustand store
- 0002: Async pexpect polling

## Open Questions
- None yet

## Change Log
- 2026-06-10: Feature doc initialized
