# Asclepius — notes for AI coding agents

- Monorepo: `backend/` (FastAPI, Python 3.12, SQLite, numpy, Pillow) and `frontend/` (Next.js 15, React 19, Tailwind 3).
- All data is synthetic and seeded. Never add real patient data, real institution names or logos.
- Run tests: `cd backend && python -m pytest -q`. E2E (starts both servers itself; first run `cd frontend && npm run e2e:install`): `cd frontend && npm run e2e` or `make e2e`. Do not use the Playwright MCP. Typecheck web: `cd frontend && npm run lint`. E2E (Playwright, starts both servers itself): `cd frontend && npm run e2e` (first time: `npm run e2e:install`). Do not use the Playwright MCP.
- Each intelligence module is a pure function; keep it that way and add tests in `backend/tests/`.
- Every new endpoint must authorise via `state.sec`, write an audit entry for patient data access, and be covered by a test.
- AI output must be cited and pass the verifier before release; do not add free-text generation paths that bypass it.
- Recharts 2 + React 19: `Cell` and animated `Bar` break; use data `fill` and `isAnimationActive={false}`. Use `legacy-peer-deps` (see `frontend/.npmrc`).
- Do not run `pkill -f` with a pattern that appears in your own command line.
