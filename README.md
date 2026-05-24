# aict

aict is a hackathon MVP for a local-first EU AI Act compliance workspace that helps a user run a cited first-pass assessment for one AI use case.

The product goal is narrow: create one case, upload supporting documents, extract and retrieve relevant evidence, generate a structured assessment with citations, and ask follow-up questions against the saved case context. The result is decision support for an internal review conversation, not a production legal determination.

Required limitation notice:

> This is a decision-support draft, not final legal advice.

## MVP Scope

In scope for the demo:

- One local AI-use-case session at a time.
- Multiple uploaded supporting documents for that case.
- Local parsing, chunking, storage, and retrieval.
- Curated EU AI Act reference excerpts bundled with the backend.
- Multi-agent first-pass analysis with named agent trace.
- Deterministic citation verification before results are saved or shown.
- Report timeline/history for saved assessments, with one active report at a time.
- Follow-up chat that uses the saved analysis, uploaded documents, and AI Act references.

Out of scope unless time remains:

- Authentication, authorization, payments, teams, or multi-tenant storage.
- Cloud deployment or managed databases.
- Full legal knowledge management, jurisdiction-by-jurisdiction advice, or final legal conclusions.
- Complex workflow approvals, redlining, or document generation.
- Production observability, audit controls, retention policies, or admin dashboards.
- Support for many simultaneous cases beyond simple local persistence.

## Local-First Architecture

The MVP should run on a developer laptop with no required cloud services.

- Backend: Python + FastAPI.
- Frontend: React + TypeScript + Vite under `frontend/`.
- Structured storage: simple local JSON repository under `backend/data/state/`.
- File storage: uploaded files, extracted text, corpus files, and indexes under `backend/data/`.
- Retrieval: local chunk store with lexical or lightweight vector search.
- LLMs: required for analysis and follow-up chat. Configure per-agent model variables before running the demo.
- Embeddings: local by default through the lightweight retrieval layer.
- Runtime: Docker Compose is the preferred demo path; manual backend/frontend commands remain available for local debugging.

The `chunks` store is the source of truth for citations. Agents may interpret retrieved evidence, but every returned citation must point to a stored chunk and pass a deterministic verifier.

Dependency source of truth:

- Backend dependencies live in `backend/pyproject.toml`: FastAPI, Uvicorn, python-dotenv, Pydantic, pypdf, python-multipart, httpx, OpenAI, Anthropic, and pytest for dev.
- Frontend dependencies live in `frontend/package.json`: React, React DOM, Vite, TypeScript, lucide-react, class-variance-authority, clsx, and tailwind-merge.
- The current frontend does not require Three.js, React Three Fiber, Playwright, Supabase, or auth libraries.

## Frontend and Backend Split

The backend owns:

- Case, document, analysis, message, and citation persistence.
- Document upload, text extraction, chunking, and retrieval.
- AI Act corpus loading and source metadata.
- Agent orchestration and shared `AnalysisResult` output.
- Citation verification.
- Follow-up chat responses and message history.

The frontend owns:

- Cases board and blank case creation.
- Use-case description editing before analysis.
- Multi-document upload UI, delete controls, lock/unlock affordances, and document status display.
- Analysis trigger and loading states.
- Cited assessment report view with collapsible sections.
- Report timeline/history controls for jumping between saved snapshots.
- Follow-up chat view after an active analysis exists.
- Agent trace, uncertainty display, copy, and Markdown export.

The frontend should call the backend through JSON APIs only. It should not run document parsing, retrieval, agent logic, or citation verification in the browser.

## Project Layout

```
aict/
├── backend/                 FastAPI app, services, agents, storage
│   ├── app/
│   │   ├── api/             HTTP routes
│   │   ├── core/            config, shared utilities
│   │   ├── models/          pydantic and persistence models
│   │   ├── services/        case/document/analysis logic
│   │   ├── agents/          multi-agent orchestration
│   │   └── storage/         JSON repository + filesystem helpers
│   ├── tests/
│   ├── data/                local JSON state, uploads, extracted text, indexes (gitignored)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                Vite + React + TypeScript app
│   └── Dockerfile
├── docker-compose.yml       local backend + frontend containers
├── Makefile                 convenience wrappers for Docker commands
├── .env.example
└── .gitignore
```

Docker Compose starts both app containers. The backend can also run standalone and the `/health` endpoint can be verified with `curl`.

## Local JSON Repository

The hackathon backend should not use SQLite or a managed database. Persist structured state as JSON files and keep uploaded/extracted documents as normal files.

Expected local state layout:

```text
backend/data/
├── state/
│   ├── cases.json
│   ├── documents.json
│   ├── active_analyses/
│   │   └── {case_id}.json
│   ├── chunks/
│   │   └── {case_id}.json
│   ├── analyses/
│   │   └── {case_id}.json
│   ├── messages/
│   │   └── {case_id}.json
│   └── evidence/
│       └── {case_id}.json
├── uploads/
│   └── {case_id}/
├── extracted/
│   └── {case_id}/
├── index/
└── corpus/
```

Use atomic writes for JSON updates: write to a temp file in the same directory, then replace the target file. The citation verifier should resolve citations to stored chunk IDs and validate snippets against the stored chunk text.

`analyses/{case_id}.json` stores the report history for a case. `active_analyses/{case_id}.json` stores the currently active analysis ID, or `null` when the case has been unlocked for document changes. Unlocking clears active chunks, evidence, messages, and search indexes, but keeps saved report snapshots in the timeline.

## Docker Run Commands

Preferred full-app start:

```bash
make up
```

Equivalent raw Compose command:

```bash
docker compose up --build
```

If ports `8001` or `5173` are already busy:

```bash
make up-alt
```

Equivalent raw Compose command:

```bash
BACKEND_PORT=8002 FRONTEND_PORT=5174 VITE_API_BASE_URL=http://localhost:8002 CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174 docker compose up --build
```

Then open:

- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:8001`
- Backend health check: `http://127.0.0.1:8001/health`

Useful container commands:

```bash
make ps
make logs
make health
make test-backend
```

Stop it with:

```bash
make down
```

The backend keeps local state in the `backend-data` Docker volume. To wipe local demo state:

```bash
make clean
```

The Compose stack does not start an Ollama container. If the backend container should call a host-running Ollama or other OpenAI-compatible server, use a URL reachable from inside Docker, for example `http://host.docker.internal:11434/v1` on Docker Desktop.

Analysis is intentionally guarded. There is no runtime mock or no-key analysis mode. Set reachable provider/API values and all analysis model variables before calling `POST /cases/{case_id}/analyze`, for example `DOCUMENT_FACT_AGENT_MODEL=vllm:llama3.1`.

## Manual Local Run Commands

Use these commands when debugging without Docker.

Backend (first run):

```bash
cp .env.example .env
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Subsequent runs:

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Verify the backend is up:

```bash
curl http://127.0.0.1:8001/health
# {"status":"ok"}
```

Run backend tests:

```bash
cd backend
. .venv/bin/activate
pytest
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Expected local URLs:

- Backend API: `http://127.0.0.1:8001`
- Backend health check: `http://127.0.0.1:8001/health`
- Frontend: `http://127.0.0.1:5173`

## Environment Variables

Expected `.env` keys:

```bash
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8001
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DATA_DIR=backend/data
STATE_DIR=backend/data/state
UPLOAD_DIR=backend/data/uploads
EXTRACTED_DIR=backend/data/extracted
INDEX_DIR=backend/data/index
AI_ACT_CORPUS_DIR=backend/data/corpus

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
VLLM_BASE_URL=http://127.0.0.1:11434/v1
VLLM_API_KEY=ollama
DOCUMENT_FACT_AGENT_MODEL=vllm:llama3.1
AI_SYSTEM_AGENT_MODEL=vllm:llama3.1
RISK_CLASSIFICATION_AGENT_MODEL=vllm:llama3.1
OBLIGATIONS_AGENT_MODEL=vllm:llama3.1
CRITIC_AGENT_MODEL=vllm:llama3.1
CHAT_AGENT_MODEL=vllm:llama3.1
EMBEDDING_PROVIDER=local

# Frontend.
VITE_API_BASE_URL=http://127.0.0.1:8001
```

For a backend running inside Docker and an Ollama server running on the host, use `VLLM_BASE_URL=http://host.docker.internal:11434/v1` instead of `127.0.0.1`.

If any required analysis model variable is empty, `POST /cases/{case_id}/analyze` returns `llm_not_configured`. If a configured provider call fails, analysis returns `llm_call_failed` instead of silently producing a heuristic report. Follow-up chat similarly requires `CHAT_AGENT_MODEL`.
