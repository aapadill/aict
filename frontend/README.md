# aict — Frontend

Vite + React + TypeScript frontend for aict, an EU AI Act compliance workspace.

## Dependency Notes

The frontend dependency source of truth is `package.json`.

Runtime dependencies are intentionally small:

- `react` and `react-dom`
- `lucide-react` for icons
- `class-variance-authority`, `clsx`, and `tailwind-merge` utility packages carried from the UI import/refactor

The current app does not use Three.js, React Three Fiber, Playwright, Supabase, auth packages, or a frontend database.

## Setup

```bash
cp .env.example .env
npm install
npm run dev
```

Set `VITE_API_BASE_URL` to your FastAPI backend (defaults to `http://localhost:8000`).

If the backend is unreachable, the UI shows an API/network error. There is no frontend mock-data fallback.

Useful checks:

```bash
npm run build
npm audit --audit-level=moderate
```

> This is a decision-support draft, not final legal advice.
