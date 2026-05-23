# AI Act Compliance Assistant — Frontend

Vite + React + TypeScript frontend for the AI Act Compliance Assistant.

## Setup

Preferred from the repo root:

```bash
make up
```

That starts the frontend container together with the backend. The frontend is exposed on `http://127.0.0.1:5173` by default and uses `VITE_API_BASE_URL=http://localhost:8000` through Docker Compose.

Manual frontend-only run:

```bash
cp .env.example .env
npm install
npm run dev
```

Set `VITE_API_BASE_URL` to your FastAPI backend (defaults to `http://localhost:8000`).

If the backend is unreachable, the UI falls back to mock data automatically (a banner is shown).

> This is a decision-support draft, not final legal advice.
