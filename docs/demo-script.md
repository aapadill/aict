# Demo Script

This script covers the intended hackathon path from a fresh case to follow-up chat.

## Sample Scenario

Demo case: an HR team wants to use an AI assistant to screen job applications, summarize CVs, and rank candidates before recruiter review.

Use three simple supporting documents for the demo:

- Product brief: describes CV parsing, candidate scoring, ranked shortlist, recruiter review, and deployment in the EU.
- Vendor note: describes model inputs, training data summary, human oversight controls, and logging.
- Governance note: describes current review process, missing bias testing, missing monitoring plan, and planned DPIA.

Expected first-pass result: the assistant should treat the use case as likely in scope, likely high-risk because it affects employment or worker management, and should surface uncertainty where the uploaded documents do not prove details such as provider role, intended purpose, validation, bias controls, or post-market monitoring.

## Demo Steps

1. Start the backend.

```bash
cd backend
. .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

2. Start the frontend.

```bash
cd frontend
npm run dev
```

3. Open `http://127.0.0.1:5173`.

4. Create a new case.

Use:

```text
Title: AI recruiting assistant for EU hiring
Description: An HR team wants to use an AI tool to summarize CVs, score applicants, and rank candidates for recruiter review across EU hiring processes.
```

5. Upload the three supporting documents.

Confirm that each document shows an uploaded or parsed status before running analysis. If parsing is asynchronous, wait for all statuses to complete.

6. Run the first-pass assessment.

Wait for the report page to load. The expected report should include:

- A short case summary.
- Extracted facts from uploaded documents.
- AI-system scope assessment.
- Risk classification with confidence.
- Likely obligations and governance observations.
- Missing information and follow-up questions.
- Citations with source snippets.
- Agent trace.
- The required limitation notice.

7. Open at least two citations.

Show that citations identify whether evidence came from an uploaded document or an AI Act reference chunk. Point out that citations are verified against stored chunks before the report is saved.

8. Review uncertainty.

Show one missing-information item, such as incomplete evidence for bias testing, provider/deployer responsibility, validation data, or human oversight. Explain that the app separates cited evidence from assumptions.

9. Ask a follow-up question in chat.

Use:

```text
What should we collect next before deciding whether this recruiting assistant can be piloted?
```

Expected answer: a prioritized list of missing documents or facts, such as intended-purpose statement, provider documentation, risk management evidence, data governance and bias testing notes, human oversight procedure, monitoring plan, and incident escalation process. The answer should cite saved analysis, uploaded documents, or AI Act references where possible.

10. Ask a second follow-up that tests uncertainty.

Use:

```text
Can we say this is definitely compliant if a recruiter reviews every recommendation?
```

Expected answer: no. Human review may be relevant, but the assistant should avoid a final legal conclusion, explain remaining uncertainty, cite available sources, and recommend reassessment when new evidence is uploaded.

## Talking Points

- MVP scope is intentionally small: one local case, multiple documents, one cited first-pass assessment, and follow-up chat.
- The backend is the authority for parsing, retrieval, agents, persistence, and citation verification.
- The frontend is a thin demo UI that renders case state, report sections, citations, agent trace, and chat.
- Agents have named roles so the audience can see how facts, legal references, classification, obligations, and critique are separated.
- Citations are not free-form model text. They must come from stored source chunks and pass deterministic verification.
- Uncertainty is a product feature. The app should say what is missing instead of pretending to produce final legal advice.
- The output is always decision support: "This is a decision-support draft, not final legal advice."

## Out of Scope for the Demo

- Login, teams, sharing, cloud hosting, and production data retention.
- Full EU AI Act corpus coverage or guaranteed legal completeness.
- Automated compliance certification.
- Complex admin workflows or approval routing.
- Polished enterprise reporting beyond simple copy or export if time remains.
