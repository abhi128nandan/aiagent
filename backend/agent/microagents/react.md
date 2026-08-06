---
triggers:
  - react
  - vite
  - next
  - next.js
---
## React (Vite/Next) Coding Guidelines
- Use modern functional components with hooks. Do not use legacy class components.
- Import CSS styles directly (e.g. `import './App.css'`).
- Always run `npx -y kill-port 3000 5173` or similar tool before launching development servers.
- Check that all component references are correctly case-matched (e.g. `App.jsx` vs `app.jsx`).
- **CRITICAL**: When scaffolding a React + Vite project (which creates default boilerplate files), you MUST replace or modify `src/App.jsx` (or `src/App.tsx`) to render the actual application UI. Do NOT leave the default Vite counter boilerplate in place. The entry rendering flow must be updated so that the new UI is immediately visible.
