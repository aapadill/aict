# Architecture

This document defines the minimum architecture for the hackathon MVP. Keep implementation choices simple and local unless a downstream ticket explicitly expands them.

## Main User Flow

1. User opens the local frontend and creates a fresh case for one AI use case.
2. User uploads multiple supporting documents, such as a product brief, vendor note, DPIA draft, or policy excerpt.
3. Backend saves the files locally, extracts text, chunks sources, and stores chunk metadata.
4. User runs the first-pass EU AI Act assessment.
5. Backend retrieves relevant uploaded-document chunks and curated AI Act reference chunks.
6. Named agents fill a shared assessment state and attach citations from retrieved chunks.
7. Citation verifier removes or flags unsupported citations before the result is saved.
8. Frontend shows a cited report with facts, risk assessment, obligations, missing information, uncertainty, and agent trace.
9. User asks a follow-up question in the same case.
10. Backend answers using the saved analysis, uploaded documents, AI Act references, and chat history.

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
- `POST /cases/{case_id}/documents`
- `GET /cases/{case_id}/documents`
- `POST /cases/{case_id}/analysis`
- `GET /cases/{case_id}/analysis/latest`
- `POST /cases/{case_id}/messages`
- `GET /cases/{case_id}/messages`

## Frontend Screens

- Case setup: title, short description, and create-case action.
- Documents: multi-file upload, upload status, parsed status, and source list.
- Assessment: run-analysis button, loading state, cited report, confidence labels, missing information, and limitation notice.
- Evidence and citations: source title, source type, location, snippet, and verification status.
- Agent trace: compact timeline of named agent actions and output summaries.
- Follow-up chat: question input, answer stream or loading state, citations, and flag when new facts may require rerunning the assessment.

The frontend should be a thin client. It renders backend state and sends user actions. It should not duplicate backend risk logic.

## Agent Workflow

Use a stateful orchestrator or graph with named agents and a shared `AnalysisResult` draft.

- `CaseIntakeAgent`: summarizes the submitted use case and identifies the assessment target.
- `DocumentFactAgent`: extracts relevant facts from uploaded documents with citations.
- `AIActReferenceAgent`: retrieves curated EU AI Act chunks relevant to the case.
- `AISystemAssessmentAgent`: assesses whether the use case appears to involve an AI system in scope.
- `RiskClassificationAgent`: drafts prohibited, high-risk, limited-risk, or unclear classification reasoning.
- `ObligationMappingAgent`: maps likely obligations and practical next steps for the apparent risk class.
- `GovernanceGapAgent`: identifies missing information, uncertainties, and governance observations.
- `CriticAgent`: reviews the draft for unsupported claims, overconfident language, and missing caveats.
- `FollowUpChatAgent`: answers later case questions from saved analysis and retrieved evidence.

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
- `Message`: chat message with role, content, citations, and timestamp.

The saved `AnalysisResult` must always include:

```text
This is a decision-support draft, not final legal advice.
```

## Implementation Constraints

- Keep the MVP single-user and local-first.
- Prefer deterministic behavior and visible fallbacks over hidden external dependencies.
- Store enough source metadata to explain every citation in the UI.
- Make confidence and uncertainty explicit.
- Avoid production-only features unless the demo path is already complete.
