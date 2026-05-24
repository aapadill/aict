from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.models.analysis import AgentState, ExtractedFact, REQUIRED_FACT_LABELS
from app.services import llm as llm_service
from app.storage import JsonRepository, repository

from .utils import (
    add_trace,
    add_unique_citations,
    build_chunk_map,
    chunks_as_citations,
    citations_for_ids,
    dedupe,
    format_chunks_for_prompt,
    uploaded_chunks,
)

_SYSTEM_PROMPT = """\
You are an EU AI Act compliance analyst performing a first-pass document review.

Your task is to extract 12 specific facts about an AI use case from the provided document chunks.
Each chunk has a chunk_id you must reference when citing evidence.

For each fact, determine:
- "value": a clear, concise description, usually under 20 words (empty string "" if not present in the documents)
- "status":
  - "found" if the documents clearly and explicitly state this information
  - "uncertain" if the documents suggest or imply it but do not state it explicitly
  - "missing" if the documents contain no relevant information for this fact
- "chunk_ids": list of chunk_ids from the provided context that support this fact (empty list if missing)

Keep values readable for a non-lawyer. Do not copy long source passages into values.
Also write a "summary": at most 2 short plain-language sentences based solely on the documents.

Respond with valid JSON only. No markdown. No text outside the JSON object.\
"""


@dataclass
class DocumentFactAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        model = settings.document_fact_agent_model
        if not model:
            raise RuntimeError("DOCUMENT_FACT_AGENT_MODEL is required.")
        return self._run_llm(state, model)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _run_llm(self, state: AgentState, model: str) -> AgentState:
        chunks = uploaded_chunks(state, repo=self.repo)
        if not chunks:
            raise RuntimeError("No uploaded-document chunks are available for fact extraction.")

        citations = chunks_as_citations(chunks)
        chunk_map = build_chunk_map(citations)

        user_prompt = (
            "Document chunks:\n"
            + format_chunks_for_prompt(citations)
            + "\n\nExtract the following 12 facts. Return ONLY this JSON structure:\n\n"
            + _FACT_JSON_SCHEMA
        )

        raw = llm_service.complete(
            model, _SYSTEM_PROMPT, user_prompt, json_mode=True, max_tokens=3000
        )
        data = llm_service.parse_json(raw)

        facts: list[ExtractedFact] = []
        for index, label in enumerate(REQUIRED_FACT_LABELS, start=1):
            fact_data = data.get("facts", {}).get(label, {})
            status = fact_data.get("status", "missing")
            if status not in ("found", "uncertain", "missing"):
                status = "missing"
            cited = citations_for_ids(fact_data.get("chunk_ids", []), chunk_map)
            facts.append(
                ExtractedFact(
                    id=f"fact_{index}",
                    label=label,
                    value=fact_data.get("value", "") or "",
                    status=status,
                    citations=cited,
                )
            )

        state.facts = facts
        add_unique_citations(
            state,
            [citation for fact in facts for citation in fact.citations],
        )
        state.summary = data.get("summary") or ""
        missing = [fact.label for fact in facts if fact.status == "missing"]
        state.missing_information = dedupe([*state.missing_information, *missing])

        found_count = sum(1 for f in facts if f.status == "found")
        add_trace(
            state,
            "DocumentFactAgent",
            "extract_facts",
            f"Extracted {found_count} facts and marked {len(missing)} missing.",
        )
        return state


# JSON schema embedded in the user prompt so the model knows the exact structure
_FACT_JSON_SCHEMA = """\
{
  "summary": "2-3 sentence summary of the use case",
  "facts": {
    "Purpose": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Users": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Affected persons": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Sector": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Input data": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Outputs": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Automation level": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Human oversight": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Deployment context": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Use of AI-generated content": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Use of GPAI/LLM": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []},
    "Potential impact on people": {"value": "...", "status": "found|uncertain|missing", "chunk_ids": []}
  }
}\
"""
