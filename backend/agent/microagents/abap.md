---
triggers:
  - abap
  - open-abap
  - abaplint
---
## ABAP Web App Developer Guidance
- Transpile using @abaplint tools. Render HTML content via `WRITE:` blocks.
- Attach a timestamp parameter when executing the module to prevent transpiled caching issues.
