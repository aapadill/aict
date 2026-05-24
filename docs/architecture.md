# Architecture

This document defines the minimum architecture for the hackathon MVP. Keep implementation choices simple and local unless a downstream ticket explicitly expands them.

## Main User Flow

1. User opens the local frontend and creates a fresh blank case from the cases board.
2. User adds a use-case description and uploads supporting documents, such as a product brief, vendor note, DPIA draft, or policy excerpt.
3. Backend saves the files locally, extracts text, chunks sources, and stores chunk metadata.
4. User runs the first-pass EU AI Act assessment.
5. Backend retrieves relevant uploaded-document chunks and curated AI Act reference chunks.
6. Named agents fill a shared assessment state and attach citations from retrieved chunks.
7. Citation verifier removes or flags unsupported citations before the result is saved.
8. Frontend shows a cited report with facts, risk assessment, obligations, missing information, uncertainty, and agent trace.
9. The saved report becomes the active analysis. Older reports remain available through the case timeline.
10. User can unlock the case for document changes. Unlocking clears the active report/chat state but keeps historical report snapshots.
11. User asks a follow-up question in the same case after an active analysis exists.
12. Backend answers using the saved analysis, uploaded documents, AI Act references, and chat history.

## Runtime Topology

The preferred demo runtime is Docker Compose from the repo root.

- `backend` container: FastAPI app on container port `8000`, exposed as `${BACKEND_PORT:-8000}`.
- `frontend` container: Vite app on container port `5173`, exposed as `${FRONTEND_PORT:-5173}`.
- `backend-data` volume: persistent local demo state for cases, uploaded files, extracted text, chunks, analysis history, active-analysis markers, evidence, and messages.
- Built-in AI Act corpus: copied into the backend image at `/app/data/corpus`.
- Runtime backend state in Docker: `/app/runtime-data`.

The same services can still be run manually for debugging, but demo docs and QA should prefer `make up` or `docker compose up --build`.

## Backend Services

- `api`: FastAPI routes for health, cases, documents, analysis, and chat.
- `core.config`: environment loading, paths, CORS origins, and provider settings.
- `storage`: JSON repository and filesystem helpers for cases, documents, chunks, analyses, evidence, and messages.
- `documents`: upload handling, text extraction, source normalization, and chunk creation.
- `retrieval`: local search over uploaded-document chunks and AI Act corpus chunks.
- `citation_verifier`: deterministic check that each citation points to a real stored chunk and that the snippet is grounded in chunk text.
- `agents.workflow`: orchestrates named agents over a shared JSON state.
- `chat`: follow-up answer generation using saved case context and retrieved evidence.

Minimum endpoints expected by the frontend:

- `GET /health`
- `POST /cases`
- `GET /cases`
- `GET /cases/{case_id}`
- `PATCH /cases/{case_id}`
- `DELETE /cases/{case_id}`
- `POST /cases/{case_id}/documents`
- `GET /cases/{case_id}/documents`
- `DELETE /cases/{case_id}/documents/{document_id}`
- `POST /cases/{case_id}/analyze`
- `GET /cases/{case_id}/analysis`
- `GET /cases/{case_id}/analyses`
- `GET /cases/{case_id}/analyses/{analysis_id}`
- `DELETE /cases/{case_id}/analysis`
- `POST /cases/{case_id}/chat`
- `GET /cases/{case_id}/messages`

## Frontend Screens

- Home: short product landing page and entry point to the cases board.
- Cases board: blank case creation, post-it style case cards, report-risk badge, and local case deletion.
- Case intake: editable use-case description before analysis.
- Documents: multi-file upload, immediate upload, file deletion before analysis, upload status, parsed status, and source list.
- Assessment: run-analysis button, loading state, cited report, confidence labels, missing information, collapsible sections, and limitation notice.
- Report timeline: saved analysis revisions with one active report and read-only historical snapshots.
- Evidence and citations: source title, source type, location, snippet, and verification status.
- Agent trace: compact timeline of named agent actions and output summaries.
- Follow-up chat: enabled only after analysis, question input, answer loading state, citations, and flag when new facts may require rerunning the assessment.

The frontend should be a thin client. It renders backend state and sends user actions. It should not duplicate backend risk logic.

## Agent Workflow

Use a stateful orchestrator with named agents and a shared `AnalysisResult` draft.

- `DocumentFactAgent`: extracts relevant facts from uploaded documents with citations and marks missing facts.
- `AISystemDefinitionAgent`: assesses whether the use case appears to involve an AI system in scope.
- `RiskClassificationAgent`: drafts prohibited, high-risk, limited-risk, minimal-risk, or unclear classification reasoning.
- `ObligationsGovernanceAgent`: maps likely roles, obligations, transparency/GPAI relevance, and practical governance observations.
- `CriticUncertaintyAgent`: reviews the draft for unsupported claims, overconfident language, contradictions, missing facts, and follow-up questions.
- Chat service: answers later case questions from saved analysis and retrieved evidence.

`CitationVerifier` is not a creative agent. It is a deterministic backend service and is the authority on whether a citation is real. If a claim cannot be cited, agents should mark it as an assumption or uncertainty instead of inventing support.

## Data Contracts Summary

Use the shared contract names from `tickets.md` unless an earlier implementation ticket creates equivalent models.

- `Case`: local session with `id`, `title`, optional `description`, and timestamps.
- `Document`: uploaded file metadata with `case_id`, `filename`, `content_type`, local paths, status, and timestamp.
- `Chunk`: source-of-truth citation unit with `source_type`, `source_title`, optional `document_id`, `location`, text, hash, and metadata.
- `Citation`: reference to a stored chunk with snippet, source metadata, optional quote hash, and `verified` flag.
- `ExtractedFact`: labeled fact with `found`, `missing`, or `uncertain` status and citations.
- `AssessmentSection`: conclusion, confidence, reasoning, citations, assumptions, and uncertainties.
- `AnalysisResult`: saved report containing summary, extracted facts, AI-system assessment, risk classification, obligations, governance observations, missing information, follow-up questions, citations, agent trace, and limitation notice.
- `AnalysisRevision`: report-history summary with analysis ID, revision number, active flag, status, timestamps, summary, risk label, and confidence.
- `Message`: chat message with role, content, citations, and timestamp.

The saved `AnalysisResult` must always include:

```text
This is a decision-support draft, not final legal advice.
```

## Implementation Constraints

- Keep the MVP single-user and local-first.
- Prefer the Docker Compose stack for demo validation; use manual commands only when debugging a specific service.
- Analysis requires configured per-agent LLM models. The workflow guard returns `llm_not_configured` when required model variables are missing.
- Failed provider calls return `llm_call_failed`; the backend should not silently replace a failed model call with a heuristic report.
- Store enough source metadata to explain every citation in the UI.
- Make confidence and uncertainty explicit.
- Avoid production-only features unless the demo path is already complete.
