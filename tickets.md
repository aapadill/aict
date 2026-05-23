# AI Act Compliance Assistant - Hackathon Tickets

These tickets are written so each one can be pasted into a coding agent as a standalone implementation prompt. Backend/local integration work is timeboxed for the hackathon; the frontend is consolidated into one external Lovable prompt that should return a downloadable `frontend/` folder.

## Global Build Assumptions

- Product: AI Act Compliance Assistant for one AI use case per session.
- Main flow: create case -> upload documents -> parse documents -> retrieve AI Act references -> run multi-agent analysis -> show cited report -> ask follow-up questions.
- Suggested frontend: React + TypeScript + Vite.
- Suggested backend: Python + FastAPI.
- Suggested storage: SQLite for app data, local filesystem for uploads, local vector/lexical retrieval for document chunks.
- Suggested agent style: stateful graph or orchestrator with named agents and shared JSON state.
- Citation rule: agents may interpret evidence, but they may not invent citations. Citation objects must come from stored source chunks and pass deterministic verification before results are saved or returned.
- Required limitation text: "This is a decision-support draft, not final legal advice."
- Keep the MVP local-first. Do not add auth, payments, cloud deployment, or multi-tenant complexity.
- If an external LLM or embedding service is unavailable, implement a clean fallback or mock so the demo path still works.

## Shared Data Contracts

Use these names unless a previous ticket already created equivalent models.

```ts
type SourceType = "uploaded_document" | "legislation" | "official_guidance" | "national_guidance" | "commentary" | "system";

type Citation = {
  id: string;
  source_id?: string;
  chunk_id?: string;
  source_type: SourceType;
  source_title: string;
  document_id?: string;
  location?: string;
  snippet: string;
  quote_hash?: string;
  verified?: boolean;
};

type ExtractedFact = {
  id: string;
  label: string;
  value: string;
  status: "found" | "missing" | "uncertain";
  citations: Citation[];
};

type AssessmentSection = {
  title: string;
  conclusion: string;
  confidence: "low" | "medium" | "high";
  reasoning: string;
  citations: Citation[];
  assumptions: string[];
  uncertainties: string[];
};

type AnalysisResult = {
  case_id: string;
  summary: string;
  extracted_facts: ExtractedFact[];
  ai_system_assessment: AssessmentSection;
  risk_classification: AssessmentSection;
  obligations: AssessmentSection[];
  governance_observations: AssessmentSection[];
  missing_information: string[];
  follow_up_questions: string[];
  citations: Citation[];
  agent_trace: {
    agent: string;
    action: string;
    output_summary: string;
  }[];
  limitation_notice: string;
};
```

---

## Task

- H01-PM-01 MVP scope, architecture, and demo path
- Timebox: 1 hour

## Instructions

Create the project planning artifacts for an AI Act Compliance Assistant hackathon MVP. The app should let a user create one AI-use-case session, upload multiple supporting documents, run a cited EU AI Act first-pass assessment, and ask follow-up questions. Write concise docs that future implementation agents can follow.

Do not build production features. Focus on the demo path and the minimum architecture needed to prove the app works.

## Implementation Details

- Create or update `README.md` with:
  - product goal
  - local-first architecture
  - frontend/backend split
  - expected local run commands
  - environment variables
  - limitation that output is decision support, not legal advice
- Create or update `docs/architecture.md` with:
  - main user flow
  - backend services
  - frontend screens
  - agent workflow
  - data contracts summary
- Create or update `docs/demo-script.md` with:
  - one sample demo scenario
  - exact steps for the hackathon demo
  - expected talking points about citations, uncertainty, and agents

## Acceptance Criteria

- [ ] MVP scope is explicit and small
- [ ] Frontend/backend split is documented
- [ ] Agent roles are named and explained
- [ ] Demo path is documented from fresh case to follow-up chat
- [ ] Bonus features are clearly marked out of scope unless time remains

## Dependencies

- Depends on: None
- Blocks: H02-BE-BOOT, H03-DATA-01, H06-AG-01, H10-FE-LOVABLE

---

## Task

- H02-BE-BOOT Backend scaffold and local dev wiring
- Timebox: 2 hours

## Instructions

Scaffold the local backend for the AI Act Compliance Assistant. Build a FastAPI backend with a clean folder structure and CORS configured for the frontend that will be generated separately by Lovable.

## Implementation Details

- Create `backend/`.
- Backend requirements:
  - FastAPI app entry point.
  - CORS enabled for the local frontend.
  - `/health` endpoint returning JSON like `{ "status": "ok" }`.
  - Config module that reads environment variables from `.env` when available.
  - Folder structure:
    - `backend/app/api/`
    - `backend/app/core/`
    - `backend/app/models/`
    - `backend/app/services/`
    - `backend/app/agents/`
    - `backend/app/storage/`
    - `backend/tests/`
- Root requirements:
  - Add `.gitignore` for Python, Node, local DB, uploads, caches, and env files.
  - Add `.env.example` with backend config keys and `VITE_API_BASE_URL` documented for the later frontend.
  - Add local backend run instructions to `README.md`.
  - Note that the frontend will be supplied as a downloadable `frontend/` folder from Lovable.

## Suggested Commands

```bash
cd backend && python -m venv .venv
cd backend && . .venv/bin/activate && pip install fastapi uvicorn python-dotenv
```

Adjust commands to the existing environment if the project already has package managers or lockfiles.

## Acceptance Criteria

- [ ] Backend starts locally and serves `/health`
- [ ] CORS is configured for a local frontend on common Vite ports
- [ ] Folder structure supports API, services, agents, and storage work
- [ ] Root docs explain how to run the backend and where the Lovable frontend will be imported

## Dependencies

- Depends on: H01-PM-01
- Blocks: H04-BE-01

---

## Task

- H03-DATA-01 Storage model and local persistence
- Timebox: 1 hour

## Instructions

Implement local persistence for the AI Act Compliance Assistant backend. Use SQLite for structured data and the local filesystem for uploaded files. Keep it simple and reliable for a 24-hour hackathon.

## Implementation Details

- Add database setup under `backend/app/storage/`.
- Use either SQLAlchemy/SQLModel or direct SQLite helpers, matching the existing backend style.
- Store these entities:
  - `cases`: id, title, description, created_at, updated_at
  - `documents`: id, case_id, filename, content_type, file_path, status, extracted_text_path, created_at
  - `chunks`: id, case_id, source_id, source_type, source_title, document_id, location, text, normalized_text_hash, metadata_json, created_at
  - `analyses`: id, case_id, status, result_json, created_at, updated_at
  - `messages`: id, case_id, role, content, citations_json, created_at
  - `evidence`: id, case_id, source_type, source_title, document_id, location, snippet, metadata_json
- The `chunks` table is the source of truth for citations. Final citations must point to real chunk IDs stored there.
- Add an initialization path that creates the DB on app startup.
- Add upload directories:
  - `backend/data/uploads/`
  - `backend/data/extracted/`
  - `backend/data/index/`
- Add repository/helper functions for create/list/get cases, create/list documents, save/get latest analysis, and save/list messages.

## API Contract Support

Later tickets should be able to call:

```python
create_case(title: str, description: str | None) -> Case
list_cases() -> list[Case]
get_case(case_id: str) -> Case | None
save_document(...) -> Document
list_documents(case_id: str) -> list[Document]
save_chunk(...) -> Chunk
get_chunk(chunk_id: str) -> Chunk | None
list_chunks(case_id: str) -> list[Chunk]
save_analysis(case_id: str, result: dict, status: str = "complete") -> Analysis
get_latest_analysis(case_id: str) -> Analysis | None
save_message(case_id: str, role: str, content: str, citations: list[dict]) -> Message
```

## Acceptance Criteria

- [ ] SQLite DB is created automatically
- [ ] Cases, documents, chunks, analyses, messages, and evidence can be persisted
- [ ] Stored chunks include enough metadata to verify citations deterministically
- [ ] Upload and extracted-text directories are created automatically
- [ ] Analysis JSON can be saved and loaded without losing nested fields
- [ ] Storage code is isolated from API route code

## Dependencies

- Depends on: H01-PM-01
- Blocks: H04-BE-01, H08-AG-03, H13-CHAT-01

---

## Task

- H04-BE-01 Case and document API
- Timebox: 2 hours

## Instructions

Build the backend API for case sessions and document uploads. Users need to create one AI-use-case session, list/open sessions, and upload multiple documents to a case.

## Implementation Details

- Add routes under `backend/app/api/`.
- Implement:
  - `POST /cases`
  - `GET /cases`
  - `GET /cases/{case_id}`
  - `POST /cases/{case_id}/documents`
  - `GET /cases/{case_id}/documents`
- `POST /cases` request:

```json
{
  "title": "Hiring CV screening assistant",
  "description": "Optional short description"
}
```

- `POST /cases` response:

```json
{
  "id": "case_...",
  "title": "...",
  "description": "...",
  "created_at": "...",
  "updated_at": "..."
}
```

- Upload endpoint:
  - Accept multipart form uploads with one or more files.
  - Allow `.pdf`, `.txt`, `.md`.
  - Reject unsupported types with a useful 400 response.
  - Save files under `backend/data/uploads/{case_id}/`.
  - Persist document rows with status `uploaded`.
- Include clear error handling:
  - case not found -> 404
  - unsupported file -> 400
  - failed file save -> 500 with safe message

## Acceptance Criteria

- [ ] User can create and list case sessions
- [ ] User can fetch one case with its documents
- [ ] User can upload multiple documents to a case
- [ ] Backend stores document metadata and file paths
- [ ] API errors are predictable and frontend-friendly

## Dependencies

- Depends on: H02-BE-BOOT, H03-DATA-01
- Blocks: H05-DOC-01, H10-FE-LOVABLE

---

## Task

- H05-DOC-01 Document parsing and fact-ready text extraction
- Timebox: 2 hours

## Instructions

Implement document text extraction for uploaded use-case documents. The analysis agents need clean text with source metadata so they can cite uploaded material later.

## Implementation Details

- Add `backend/app/services/document_parser.py`.
- Implement parsing for:
  - PDFs using a practical Python library such as `pypdf` or `pymupdf`
  - `.txt`
  - `.md`
- Add a backend service function:

```python
extract_document_text(document_id: str) -> ExtractedDocument
```

- Suggested return shape:

```python
{
  "document_id": "...",
  "source_title": "filename.pdf",
  "text": "...",
  "pages": [
    { "page": 1, "text": "..." }
  ],
  "status": "parsed",
  "warnings": []
}
```

- Save extracted text to `backend/data/extracted/{case_id}/{document_id}.txt`.
- Preserve page numbers where possible for citations.
- Mark documents as:
  - `parsed`
  - `empty`
  - `unreadable`
  - `failed`
- Add an endpoint or internal helper that parses all uploaded docs for a case:

```python
parse_case_documents(case_id: str) -> list[ExtractedDocument]
```

## Acceptance Criteria

- [ ] Backend extracts text from PDFs, TXT, and Markdown
- [ ] Extracted text is saved or cached
- [ ] Page/source metadata is preserved where available
- [ ] Empty, scanned, or unreadable documents are flagged
- [ ] Parsing can be triggered by later analysis workflow without manual steps

## Dependencies

- Depends on: H04-BE-01
- Blocks: H07-RAG-01, H08-AG-03

---

## Task

- H06-AG-01 Shared agent state and output schema
- Timebox: 1 hour

## Instructions

Define the shared state and output schemas for the multi-agent AI Act analysis workflow. The frontend and backend should agree on a stable `AnalysisResult` shape.

## Implementation Details

- Add schema/model definitions in backend, for example:
  - `backend/app/models/analysis.py`
  - or equivalent Pydantic models
- Include models for:
  - `Citation`
  - `ExtractedFact`
  - `AssessmentSection`
  - `AgentTraceEvent`
  - `AnalysisResult`
  - `AgentState`
- `Citation` must include enough fields for deterministic verification: `id`, optional `source_id`, optional `chunk_id`, `source_type`, `source_title`, optional `document_id`, optional `location`, `snippet`, optional `quote_hash`, and optional `verified`.
- Required fact labels:
  - Purpose
  - Users
  - Affected persons
  - Sector
  - Input data
  - Outputs
  - Automation level
  - Human oversight
  - Deployment context
  - Use of AI-generated content
  - Use of GPAI/LLM
  - Potential impact on people
- Required analysis sections:
  - Use-case summary
  - AI-system definition assessment
  - Risk classification
  - Roles and obligations
  - Governance observations
  - Missing information
  - Follow-up questions
  - Citations
  - Agent trace
- Add a frontend TypeScript mirror of these types when frontend exists, for example `frontend/src/types/analysis.ts`.

## Acceptance Criteria

- [ ] Backend has typed schemas for citations, facts, assessment sections, and full analysis results
- [ ] State includes facts, evidence, assessment, obligations, assumptions, uncertainties, follow-up questions, and final report
- [ ] Schema can serialize to JSON
- [ ] Frontend type definitions match backend JSON shape
- [ ] Limitation notice field is included

## Dependencies

- Depends on: H01-PM-01
- Blocks: H08-AG-03, H09-AG-04, H10-FE-LOVABLE

---

## Task

- H07-RAG-01 AI Act corpus, chunking, retrieval, and citations
- Timebox: 2 hours

## Instructions

Implement the retrieval layer for uploaded documents and built-in EU AI Act reference material. The app must return source snippets with metadata so the analysis can be grounded and cited.

## Implementation Details

- Add built-in corpus files under `backend/data/corpus/`.
- Include at least a small curated local corpus with these source categories:
  - official EU AI Act regulation excerpts
  - AI-system definition guidance placeholder or excerpt
  - prohibited-practices guidance placeholder or excerpt
  - transparency/labelling guidance placeholder or excerpt
  - GPAI obligations placeholder or excerpt
- If full source ingestion is not available in the hackathon, create clearly labelled curated excerpts and TODOs for full corpus ingestion.
- Add chunking service:

```python
chunk_text(text: str, metadata: dict) -> list[Chunk]
```

- Add retrieval service:

```python
index_case(case_id: str) -> None
search_case(case_id: str, query: str, source_types: list[str] | None = None, limit: int = 5) -> list[Citation]
```

- Add deterministic citation verifier service:

```python
verify_citation(citation: Citation) -> VerifiedCitationResult
verify_citations(citations: list[Citation]) -> list[Citation]
verify_analysis_citations(result: AnalysisResult) -> AnalysisResult
```

- Verification rules:
  - Do not rely on an LLM or agent to validate citations.
  - Do not use raw `grep` over arbitrary files as the primary verifier. Grep-style normalized substring search is acceptable as a fallback, but the primary verification path is resolving a citation to a persisted chunk ID and validating the snippet/hash against that chunk text.
  - Citation `id` or `chunk_id` must resolve to a stored chunk row.
  - Uploaded-document citations must point to an existing uploaded document.
  - Regulatory citations must point to a stored built-in corpus chunk.
  - `source_type`, `source_title`, and `location` must match the stored chunk metadata.
  - `snippet` must match the stored chunk text after deterministic normalization: lowercase, collapse whitespace, normalize quotes/dashes, strip leading/trailing punctuation.
  - Store or recompute `quote_hash` from the normalized snippet when possible.
  - If exact normalized substring matching fails, allow only a strict near-match fallback, such as token overlap above a high threshold. Record that fallback in metadata.
  - If verification fails, remove the citation from the result and add an uncertainty like "A generated citation could not be verified against the stored source text."
  - Do not use an LLM to decide whether a citation is real.

- Retrieval can be:
  - vector search if dependencies/API keys are ready
  - lexical/BM25/simple scoring if speed is more important
- Required citation metadata:
  - stable id
  - source id or chunk id
  - source type
  - source title
  - document id if uploaded source
  - page/section/location if available
  - snippet
  - optional normalized quote hash
- Make source separation explicit:
  - uploaded-document facts
  - legislation/reference material
  - optional/commentary material

## Acceptance Criteria

- [ ] Built-in corpus exists locally and is labelled by source type
- [ ] Uploaded documents and reference corpus can be chunked
- [ ] Search returns relevant snippets for a query
- [ ] Retrieval results include source title, source type, snippet, and location metadata
- [ ] Citation objects match the shared schema
- [ ] Citation verifier confirms citations against stored chunks without using an agent or LLM
- [ ] Invalid citations are stripped or marked unsupported before reaching the final analysis

## Dependencies

- Depends on: H05-DOC-01
- Blocks: H08-AG-03, H09-AG-04, H10-FE-LOVABLE, H13-CHAT-01

---

## Task

- H08-AG-03 Core analysis agents
- Timebox: 2 hours

## Instructions

Implement the core multi-agent analysis functions for the AI Act Compliance Assistant. The goal is to produce a structured first-pass assessment from uploaded documents and retrieved AI Act references.

## Implementation Details

- Add agent modules under `backend/app/agents/`.
- Implement these agents as separate functions/classes with clear names:
  - `DocumentFactAgent`
  - `AISystemDefinitionAgent`
  - `RiskClassificationAgent`
  - `ObligationsGovernanceAgent`
- Each agent should:
  - read shared `AgentState`
  - write structured output back to state
  - add an `agent_trace` event
  - cite evidence where possible using only `Citation` objects returned by retrieval
  - never fabricate source titles, page numbers, snippets, citation IDs, or legal references
- `DocumentFactAgent`:
  - uses extracted uploaded document text
  - extracts required facts
  - marks missing facts as `status: "missing"`
  - cites uploaded-document snippets
- `AISystemDefinitionAgent`:
  - determines whether the described technology appears to qualify as an AI system
  - retrieves and cites AI-system definition material
  - records confidence and uncertainty
- `RiskClassificationAgent`:
  - checks unacceptable, high, limited, and minimal risk
  - looks for sector-specific signals like employment, education, essential services, biometrics, law enforcement, migration, critical infrastructure
  - cites both use-case facts and regulatory references
- `ObligationsGovernanceAgent`:
  - identifies possible provider/deployer roles
  - checks transparency/labelling/GPAI relevance
  - produces practical governance observations: documentation, risk management, logging, monitoring, human oversight, accountability
- Use a configured LLM if available. If not available, implement deterministic heuristic output good enough for demo/testing.

## Output Requirements

- The agents must fill:
  - `summary`
  - `extracted_facts`
  - `ai_system_assessment`
  - `risk_classification`
  - `obligations`
  - `governance_observations`
  - `citations`
  - `agent_trace`

## Acceptance Criteria

- [ ] Each agent is a distinct module/function/class
- [ ] Agents exchange structured state instead of one giant prompt only
- [ ] Extracted facts cover the required fact labels
- [ ] Risk and obligations analysis includes citations when possible
- [ ] Agents only reuse retrieval-provided citations and do not generate citations free-form
- [ ] Outputs include confidence, assumptions, and uncertainties

## Dependencies

- Depends on: H03-DATA-01, H05-DOC-01, H06-AG-01, H07-RAG-01
- Blocks: H09-AG-04, H10-FE-LOVABLE

---

## Task

- H09-AG-04 Critic agent and analysis endpoint
- Timebox: 2 hours

## Instructions

Wire the agent workflow into an analysis endpoint and add a critic agent. The backend should run the full analysis from one endpoint, save the result, and return structured JSON for the frontend.

## Implementation Details

- Add `CriticUncertaintyAgent`.
- Critic responsibilities:
  - detect missing facts needed for classification
  - flag weak evidence
  - flag contradictions between uploaded docs if visible
  - downgrade confidence where evidence is weak
  - produce targeted follow-up questions
  - ensure limitation notice is present
- Add an orchestrator, for example `backend/app/agents/workflow.py`.
- Orchestrator flow:

```text
load case
parse documents if needed
index/retrieve evidence if needed
DocumentFactAgent
AISystemDefinitionAgent
RiskClassificationAgent
ObligationsGovernanceAgent
CriticUncertaintyAgent
assemble AnalysisResult
CitationVerifier
save AnalysisResult
return AnalysisResult
```

- Add a deterministic citation verification gate before saving:
  - collect all citations from facts, sections, obligations, governance notes, and top-level citations
  - verify each citation against the stored chunk table/corpus index
  - remove citations that cannot be resolved to stored text
  - add an uncertainty when a conclusion loses citation support
  - lower confidence when important citations are removed
  - save only verified citations in the final `AnalysisResult`
- The critic agent may flag unsupported reasoning, but the verifier is the authority on whether a citation is real.

- Implement endpoint:
  - `POST /cases/{case_id}/analyze`
  - `GET /cases/{case_id}/analysis`
- `POST /analyze` should:
  - return 404 if case does not exist
  - return useful error if no documents are uploaded
  - persist analysis status/result
  - return the full `AnalysisResult`
- `GET /analysis` should return the latest saved analysis or 404 if none exists.

## Acceptance Criteria

- [ ] `POST /cases/{case_id}/analyze` runs the full workflow
- [ ] `GET /cases/{case_id}/analysis` returns latest result
- [ ] Critic flags missing information, uncertainty, weak evidence, and overconfidence
- [ ] Follow-up questions are generated
- [ ] Analysis result is saved and matches the shared schema
- [ ] Agent trace shows named agent steps and short output summaries
- [ ] Final saved analysis contains only citations verified against stored chunks
- [ ] Invalid or hallucinated citations are removed deterministically and reflected as uncertainty

## Dependencies

- Depends on: H06-AG-01, H07-RAG-01, H08-AG-03
- Blocks: H10-FE-LOVABLE, H14-QA-01

---

## Task

- H10-FE-LOVABLE Complete frontend app for Lovable
- Timebox: external Lovable build

## Instructions

Build a complete React + TypeScript frontend for an app called "AI Act Compliance Assistant". This app is for a 24-hour hackathon. The frontend must be something we can download as a ZIP and drop into an existing repo as a `frontend/` folder.

Important constraints:

- Build only the frontend.
- Do not create a backend.
- Do not use Supabase, Firebase, auth, database tables, edge functions, or server-side storage.
- Use REST API calls to a FastAPI backend.
- The API base URL must come from `VITE_API_BASE_URL`, defaulting to `http://localhost:8000`.
- The deliverable must be a self-contained Vite React TypeScript app in a folder named `frontend`.
- Include `package.json`, `src/`, `index.html`, Vite config, TypeScript config, and `.env.example`.
- Use mock data only as a fallback when the backend is unavailable. The real path must call the API contracts below.
- The first screen should be the usable app workspace, not a marketing landing page.
- The UI should feel like a serious compliance review tool: compact, structured, readable, and work-focused.
- Include the visible limitation text: "This is a decision-support draft, not final legal advice."

What the frontend must do:

1. Case dashboard
   - Show existing cases from `GET /cases`.
   - Let the user create a case with title and optional description using `POST /cases`.
   - Let the user open a case workspace.

2. Case workspace
   - Show case title, description, documents, analysis status, and action buttons.
   - Let the user upload multiple files using `POST /cases/{case_id}/documents`.
   - Supported file types in the UI: PDF, TXT, Markdown.
   - Show uploaded document names and statuses.
   - Provide a clear "Run analysis" button that calls `POST /cases/{case_id}/analyze`.
   - Load latest analysis from `GET /cases/{case_id}/analysis`.

3. Assessment report
   - Render the structured `AnalysisResult` returned by the backend.
   - Sections:
     - limitation notice
     - use-case summary
     - extracted facts
     - AI-system definition assessment
     - preliminary risk classification
     - roles and obligations
     - governance observations
     - missing information
     - follow-up questions
     - agent trace
   - For each assessment section show conclusion, confidence, reasoning, assumptions, uncertainties, and citations.

4. Evidence and citations
   - Show citations grouped by source type:
     - uploaded documents
     - legislation
     - official guidance
     - national guidance
     - commentary
     - system
   - Each citation should show source title, source type, location if available, and snippet.
   - Make uploaded-document facts visually distinct from regulatory references.
   - Make weak/uncertain conclusions visibly distinct from high-confidence conclusions.

5. Follow-up chat
   - Show chat history from `GET /cases/{case_id}/messages`.
   - Send a message using `POST /cases/{case_id}/chat`.
   - Show assistant answer, citations, detected new facts, and reassessment recommendation.
   - If reassessment is recommended, show a "Run analysis again" action.

6. Export/copy report
   - Add a button to copy the full report as Markdown.
   - Add a button to download the report as `ai-act-assessment-{case_id}.md`.
   - Export must include summary, facts, assessment, obligations, governance observations, missing information, follow-up questions, citations, agent trace, and limitation notice.

7. UX and states
   - Include clear empty states for no cases, no documents, no analysis, and no chat messages.
   - Include loading states for create case, upload, run analysis, load analysis, send chat, and export.
   - Include readable API error messages.
   - Buttons should not resize when loading.
   - Text must not overflow cards/buttons on mobile or desktop.
   - Make the layout responsive.
   - Use a restrained professional palette, not a marketing hero design.

## Implementation Details

Expected downloadable deliverable:

```text
frontend/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  .env.example
  src/
    main.tsx
    App.tsx
    api/client.ts
    types/api.ts
    utils/exportReport.ts
    components/
      CaseDashboard.tsx
      CaseWorkspace.tsx
      DocumentUploader.tsx
      AnalysisReport.tsx
      EvidencePanel.tsx
      ChatPanel.tsx
      AgentTrace.tsx
      EmptyState.tsx
      LoadingButton.tsx
```

Use these TypeScript types:

```ts
export type SourceType =
  | "uploaded_document"
  | "legislation"
  | "official_guidance"
  | "national_guidance"
  | "commentary"
  | "system";

export type Case = {
  id: string;
  title: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentRecord = {
  id: string;
  case_id: string;
  filename: string;
  content_type?: string | null;
  status: "uploaded" | "parsed" | "empty" | "unreadable" | "failed";
  created_at: string;
};

export type Citation = {
  id: string;
  source_id?: string;
  chunk_id?: string;
  source_type: SourceType;
  source_title: string;
  document_id?: string;
  location?: string;
  snippet: string;
  quote_hash?: string;
  verified?: boolean;
};

export type ExtractedFact = {
  id: string;
  label: string;
  value: string;
  status: "found" | "missing" | "uncertain";
  citations: Citation[];
};

export type AssessmentSection = {
  title: string;
  conclusion: string;
  confidence: "low" | "medium" | "high";
  reasoning: string;
  citations: Citation[];
  assumptions: string[];
  uncertainties: string[];
};

export type AgentTraceEvent = {
  agent: string;
  action: string;
  output_summary: string;
};

export type AnalysisResult = {
  case_id: string;
  summary: string;
  extracted_facts: ExtractedFact[];
  ai_system_assessment: AssessmentSection;
  risk_classification: AssessmentSection;
  obligations: AssessmentSection[];
  governance_observations: AssessmentSection[];
  missing_information: string[];
  follow_up_questions: string[];
  citations: Citation[];
  agent_trace: AgentTraceEvent[];
  limitation_notice: string;
};

export type ChatMessage = {
  id: string;
  case_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: Citation[];
  created_at: string;
};

export type ChatResponse = {
  role: "assistant";
  content: string;
  citations: Citation[];
  new_facts_detected: string[];
  reassessment_recommended: boolean;
};
```

Use these API functions in `src/api/client.ts`:

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

createCase(input: { title: string; description?: string }): Promise<Case>
listCases(): Promise<Case[]>
getCase(caseId: string): Promise<Case & { documents?: DocumentRecord[] }>
uploadDocuments(caseId: string, files: File[]): Promise<DocumentRecord[]>
listDocuments(caseId: string): Promise<DocumentRecord[]>
runAnalysis(caseId: string): Promise<AnalysisResult>
getAnalysis(caseId: string): Promise<AnalysisResult | null>
getMessages(caseId: string): Promise<ChatMessage[]>
sendChatMessage(caseId: string, message: string): Promise<ChatResponse>
```

Expected backend endpoints:

```text
GET    /health
POST   /cases
GET    /cases
GET    /cases/{case_id}
POST   /cases/{case_id}/documents
GET    /cases/{case_id}/documents
POST   /cases/{case_id}/analyze
GET    /cases/{case_id}/analysis
POST   /cases/{case_id}/chat
GET    /cases/{case_id}/messages
```

Design notes:

- Use tabs or a segmented control inside the workspace for Report, Evidence, Chat, and Agent Trace.
- Keep cards at 8px radius or less.
- Use simple icons where helpful for upload, analyze, copy, download, chat, warning, and check states.
- Avoid decorative hero sections, gradient backgrounds, marketing copy, and oversized headings.
- Prefer dense but readable compliance-tool layout.
- Include mock/fallback data in a clearly isolated file such as `src/api/mockData.ts`; do not let mock mode hide real API errors when the backend is configured.

## Acceptance Criteria

- [ ] Lovable output is a downloadable ZIP containing a `frontend/` folder
- [ ] App is Vite + React + TypeScript
- [ ] No backend, Supabase, Firebase, auth, database, or server functions are included
- [ ] API base URL uses `VITE_API_BASE_URL`
- [ ] User can create/open cases, upload documents, trigger analysis, view report, inspect evidence, chat, and export/copy report
- [ ] UI renders the full `AnalysisResult` contract
- [ ] UI separates facts, citations, assumptions, uncertainties, generated interpretation, and agent trace
- [ ] Frontend has clear loading, empty, and error states
- [ ] Downloaded `frontend/` can be copied directly into this repo and run with `npm install && npm run dev`

## Dependencies

- Depends on: H04-BE-01, H06-AG-01, H09-AG-04
- Blocks: H14-QA-01, H15-POLISH-01

---

## Task

- H13-CHAT-01 Follow-up chat and reassessment hooks
- Timebox: 2 hours

## Instructions

Implement the backend follow-up chat API inside a case session. The chat should use saved analysis context, uploaded documents, and AI Act references. It should cite sources where possible and flag new facts for reassessment. The frontend is handled separately by the Lovable frontend ticket.

## Implementation Details

- Add `POST /cases/{case_id}/chat`
- Add `GET /cases/{case_id}/messages`
- Request:

```json
{
  "message": "Does this look high-risk if it is used for hiring?"
}
```

- Response:

```json
{
  "role": "assistant",
  "content": "...",
  "citations": [],
  "new_facts_detected": [],
  "reassessment_recommended": false
}
```

- Chat behavior:
  - load latest analysis
  - retrieve relevant uploaded and regulatory chunks
  - answer with citations when relevant
  - use only citations returned by retrieval
  - run the deterministic citation verifier before returning assistant citations
  - avoid final legal-advice language
  - if user provides new factual information, store it as a message and set `reassessment_recommended: true`
- Save both user and assistant messages in SQLite.
- Keep response shape exactly aligned with the Lovable frontend contract.

## Acceptance Criteria

- [ ] Backend accepts follow-up questions inside a case
- [ ] Chat uses uploaded documents, AI Act corpus, and saved analysis context
- [ ] Chat answers include citations where relevant
- [ ] Chat citations are verified against stored chunks before being returned
- [ ] New user-provided facts are stored or flagged for reassessment
- [ ] Message history endpoint returns stored case messages

## Dependencies

- Depends on: H03-DATA-01, H07-RAG-01, H09-AG-04
- Blocks: H14-QA-01, H15-POLISH-01

---

## Task

- H14-QA-01 End-to-end demo validation
- Timebox: 1 hour

## Instructions

Validate the end-to-end demo path and fix blocking issues only. Do not add new features unless needed to make the demo work.

## Implementation Details

- Create a small sample use-case document under `samples/`.
- Recommended sample scenario:
  - "AI tool screens job applications, ranks candidates, and summarizes CVs for recruiters."
  - Include facts about purpose, users, affected persons, input data, output, automation level, human oversight, and uncertainty.
- Run the full flow:
  - start backend
  - start frontend
  - create case
  - upload sample document
  - run analysis
  - inspect report
  - ask one follow-up chat question
- Fix only issues that block:
  - app startup
  - upload
  - parsing
  - analysis
  - report rendering
  - chat
- Verify citation grounding:
  - pick one citation shown in the UI
  - confirm its `chunk_id` exists in storage
  - confirm its snippet appears in the stored chunk after normalization
  - confirm a fake citation ID fails verification
- Add a short `docs/qa-notes.md` with:
  - commands run
  - what worked
  - known issues

## Acceptance Criteria

- [ ] Fresh case can be created
- [ ] Sample documents can be uploaded
- [ ] Analysis completes without manual backend intervention
- [ ] Report includes citations, uncertainty, and follow-up questions
- [ ] Follow-up chat works for at least one targeted question
- [ ] Citation verifier accepts a real citation and rejects a fake citation
- [ ] QA notes document remaining risks

## Dependencies

- Depends on: H09-AG-04, H10-FE-LOVABLE, H13-CHAT-01
- Blocks: H15-POLISH-01, H16-DEMO-01

---

## Task

- H15-POLISH-01 Import Lovable frontend and final integration polish
- Timebox: 1 hour

## Instructions

Import the Lovable-generated frontend into this repo and perform final integration polish. Do not redesign the frontend or add broad new features. The goal is to make the downloaded `frontend/` work cleanly against the backend.

## Implementation Details

- Copy the downloaded Lovable `frontend/` folder into the repo root.
- Verify `frontend/.env.example` includes `VITE_API_BASE_URL=http://localhost:8000`.
- Run `npm install` and `npm run dev` from `frontend/`.
- Fix only integration mismatches:
  - endpoint paths
  - request/response field names
  - CORS assumptions
  - missing loading/error handling that blocks the demo
  - report export/copy if Lovable omitted it
- Confirm export includes:
  - case title
  - limitation notice
  - summary
  - extracted facts
  - AI-system assessment
  - risk classification
  - roles and obligations
  - governance observations
  - missing information
  - follow-up questions
  - citations
  - agent trace
- Add or update known limitations:
  - not legal advice
  - first-pass assessment only
  - depends on uploaded document quality
  - EU AI Act practical interpretation is still developing
  - corpus may be curated in MVP

## Acceptance Criteria

- [ ] Lovable `frontend/` is present in the repo
- [ ] Frontend runs with `npm install && npm run dev`
- [ ] Frontend calls backend using `VITE_API_BASE_URL`
- [ ] Create case, upload, analyze, evidence view, chat, and export work against the backend
- [ ] Known limitations are documented in the app or README

## Dependencies

- Depends on: H10-FE-LOVABLE, H13-CHAT-01, H14-QA-01
- Blocks: H16-DEMO-01

---

## Task

- H16-DEMO-01 Final QA and pitch prep
- Timebox: 1 hour

## Instructions

Prepare the final hackathon demo. Verify the full path, document exactly how to run it, and write a short pitch explaining the agentic workflow.

## Implementation Details

- Re-run the full demo path from a clean-ish local state:
  - backend starts
  - frontend starts
  - create case
  - upload sample document
  - run analysis
  - inspect citations/uncertainty
  - ask follow-up question
  - export/copy report
- Update `docs/demo-script.md` with:
  - 2-minute demo script
  - 5-minute demo script
  - expected sample inputs
  - expected output highlights
- Add an "Agentic Workflow" explanation:
  - DocumentFactAgent extracts facts
  - AISystemDefinitionAgent checks AI-system definition
  - RiskClassificationAgent maps likely risk class
  - ObligationsGovernanceAgent maps roles and governance
  - CriticUncertaintyAgent challenges weak evidence and asks follow-up questions
- Add final known issues and next steps.
- Do not start large new feature work in this ticket.

## Acceptance Criteria

- [ ] Full demo path works from fresh case to exported report
- [ ] Demo script covers upload, cited assessment, uncertainty, and follow-up chat
- [ ] Agent roles and autonomous decisions can be explained
- [ ] Remaining risks and unfinished bonus features are documented
- [ ] README has current local run instructions

## Dependencies

- Depends on: H14-QA-01, H15-POLISH-01
- Blocks: None
