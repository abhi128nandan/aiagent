# Decision 0001: Shared WebSocket + Zustand Store

## Date
2026-06-10

## Status
Accepted

## Context
Frontend needs real-time terminal I/O and agent status updates.
Multiple components need access to the same WebSocket connection.

## Decision
Use a single shared WebSocket connection managed via a Zustand store.
All components subscribe to the store, not the socket directly.

## Consequences
- Single connection reduces overhead
- Zustand makes state accessible anywhere in React tree
- Socket logic centralized in one store file
