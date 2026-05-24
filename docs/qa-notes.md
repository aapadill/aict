# QA Notes

Date: 2026-05-24

## Commands Run

Docker configuration verification run:

```bash
docker compose config --quiet
make -n up
make -n test-backend
```

Current Docker demo path to run:

```bash
make up
make health
make ps
make logs
make test-backend
```

Equivalent raw commands to run:

```bash
docker compose up --build
curl -sS http://127.0.0.1:8000/health
docker compose ps
docker compose logs -f
docker compose run --rm backend python -m pytest
```

Manual backend tests previously run:

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m pytest tests/test_end_to_end_demo.py
```

```bash
cd frontend
npm --cache /private/tmp/aict-npm-cache install
npm run build
npm audit --audit-level=moderate
```

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -sS http://127.0.0.1:8000/health
```

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
curl -I -sS http://127.0.0.1:5173/
```

## What Worked

- Docker Compose is now the documented default runtime for backend and frontend together.
- The Makefile provides `make up`, `make up-alt`, `make down`, `make clean`, `make health`, and `make test-backend`.
- `docker compose config --quiet` completed successfully.
- Backend health endpoint returned `{"status":"ok"}`.
- Frontend Vite server returned `HTTP/1.1 200 OK`.
- Backend test suite passed: `52 passed`.
- Frontend production build completed successfully.
- Frontend dependency audit currently reports two moderate vulnerabilities through Vite/esbuild dev-server dependencies; the suggested fix is a breaking Vite upgrade and is not blocking for the local hackathon demo.
- Sample use-case document exists at `samples/hiring_cv_screening_use_case.md`.
- End-to-end API demo test passed:
  - fresh case creation
  - sample document upload
  - analysis generation without manual backend intervention
  - report includes citations, uncertainty, follow-up questions, and agent trace
  - follow-up chat returns assistant response and citations
  - citation verifier accepts a real citation and rejects a fake citation

## Known Issues And Risks

- Docker image builds require package registry access the first time dependencies are installed.
- Containerized backend state lives in the `backend-data` Docker volume, not directly in `backend/data/state/`; use `make clean` to wipe demo state.
- The Compose stack does not start Ollama. A host model server must be reachable from inside the backend container, for example via `host.docker.internal` on Docker Desktop, and per-agent model environment variables must be configured.
- Frontend dependency install required npm registry access. In a restricted network, run `npm install` before the demo or keep `node_modules` available locally.
- The frontend dependency tree intentionally does not include Three.js, React Three Fiber, Playwright, Supabase, auth packages, or a frontend database.
- The AI Act corpus is curated excerpts/placeholders, not full official corpus ingestion.
- `POST /analyze` is guarded: without all required analysis model variables, it returns `llm_not_configured`. Failed configured model calls return `llm_call_failed`.
- Browser-level manual testing was limited to confirming the Vite app boots; the full user flow is covered by backend API tests and frontend build validation.
