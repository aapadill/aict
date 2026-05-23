# AI Act Compliance Assistant

Hackathon MVP for a local-first assistant that helps a user run a cited first-pass EU AI Act assessment for one AI use case.

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
- Frontend: React + TypeScript + Vite, supplied later as a downloadable `frontend/` folder.
- Structured storage: SQLite under `backend/data/`.
- File storage: uploaded and extracted files under `backend/data/`.
- Retrieval: local chunk store with lexical or lightweight vector search.
- LLM and embeddings: optional. If unavailable, the backend should expose a mock or fallback path so the demo still works.

The `chunks` store is the source of truth for citations. Agents may interpret retrieved evidence, but every returned citation must point to a stored chunk and pass a deterministic verifier.

## Frontend and Backend Split

The backend owns:

- Case, document, analysis, message, and citation persistence.
- Document upload, text extraction, chunking, and retrieval.
- AI Act corpus loading and source metadata.
- Agent orchestration and shared `AnalysisResult` output.
- Citation verification.
- Follow-up chat responses and message history.

The frontend owns:

- Case creation form.
- Multi-document upload UI and document status display.
- Analysis trigger and loading states.
- Cited assessment report view.
- Follow-up chat view.
- Agent trace and uncertainty display.
- Copy/export affordances if time allows.

The frontend should call the backend through JSON APIs only. It should not run document parsing, retrieval, agent logic, or citation verification in the browser.

## Expected Local Run Commands

These commands describe the intended local developer flow after the backend and frontend tickets are implemented.

Backend:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Expected local URLs:

- Backend API: `http://127.0.0.1:8000`
- Backend health check: `http://127.0.0.1:8000/health`
- Frontend: `http://127.0.0.1:5173`

## Environment Variables

Expected `.env` keys:

```bash
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DATA_DIR=backend/data
SQLITE_PATH=backend/data/app.db
UPLOAD_DIR=backend/data/uploads
EXTRACTED_DIR=backend/data/extracted
INDEX_DIR=backend/data/index
AI_ACT_CORPUS_DIR=backend/data/corpus

# Optional. Use mock or local fallback when absent.
LLM_PROVIDER=mock
OPENAI_API_KEY=
EMBEDDING_PROVIDER=local

# Frontend.
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Do not fail the demo path only because an external model or embedding service is unavailable. Prefer visible fallback behavior with lower confidence and clear uncertainty.
