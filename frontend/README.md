# AI Act Compliance Assistant — Frontend

Vite + React + TypeScript frontend for the AI Act Compliance Assistant.

## Setup

```bash
cp .env.example .env
npm install
npm run dev
```

Set `VITE_API_BASE_URL` to your FastAPI backend (defaults to `http://localhost:8000`).

If the backend is unreachable, the UI falls back to mock data automatically (a banner is shown).

> This is a decision-support draft, not final legal advice.
