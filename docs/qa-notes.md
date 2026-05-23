# QA Notes

Date: 2026-05-23

## Commands Run

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m pytest tests/test_end_to_end_demo.py
```

```bash
cd frontend
npm --cache /private/tmp/aict-npm-cache install
npm run build
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

- Backend health endpoint returned `{"status":"ok"}`.
- Frontend Vite server returned `HTTP/1.1 200 OK`.
- Backend test suite passed: `40 passed`.
- Frontend production build completed successfully.
- Sample use-case document exists at `samples/hiring_cv_screening_use_case.md`.
- End-to-end API demo test passed:
  - fresh case creation
  - sample document upload
  - analysis generation without manual backend intervention
  - report includes citations, uncertainty, follow-up questions, and agent trace
  - follow-up chat returns assistant response and citations
  - citation verifier accepts a real citation and rejects a fake citation

## Known Issues And Risks

- Frontend dependency install required npm registry access. In a restricted network, run `npm install` before the demo or keep `node_modules` available locally.
- `npm audit` reported two moderate vulnerabilities in the frontend dependency tree. Not blocking for the hackathon demo, but should be reviewed later.
- The AI Act corpus is curated excerpts/placeholders, not full official corpus ingestion.
- Analysis is deterministic heuristic decision support, not legal advice.
- Browser-level manual testing was limited to confirming the Vite app boots; the full user flow is covered by backend API tests and frontend build validation.
