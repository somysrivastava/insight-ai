# InsightAI — Frontend

A demo-optimized React client for InsightAI's 3 flagship flows: upload
a dataset and ask it questions in plain English, pin results to a
dashboard, and export or schedule reports. Single-user focus, no
workspace management UI — see `docs/ADR.md` (ADR-021, gitignored,
local-only) for the reasoning behind that scope and every other
decision in this build.

## Stack

React 18 · Vite · TypeScript · Tailwind CSS · React Query · Recharts ·
React Router · Axios.

## Running it

Requires the backend running separately (see the repo root's own
README/`docker-compose.yml`) — this app talks to it directly over
HTTP, there's no dev-time proxy.

```bash
npm install
cp .env.example .env   # VITE_API_URL defaults to http://localhost:8000
npm run dev
```

Or via Docker Compose from the repo root: `docker compose up frontend`
(brings up its own dependencies too). Runs Vite's dev server with HMR
— there's no production build/serving path yet, that's Day 29.

## Structure

```
src/
├── api/          one module per backend domain; client.ts holds the
│                  shared axios instance (JWT interceptor, 401 handling)
├── hooks/        React Query wrappers around api/
├── context/      AuthContext — token state
├── components/   shared UI, including ResultRenderer (chart/table/
│                  stat, shape-detected from the AI query response)
├── pages/        one per route
└── types/api.ts  hand-kept in sync with app/schemas/*.py
```
