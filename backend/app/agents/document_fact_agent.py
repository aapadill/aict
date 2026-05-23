from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.models.analysis import AgentState, ExtractedFact, FactLabel, REQUIRED_FACT_LABELS
from app.services import llm as llm_service
from app.storage import JsonRepository, repository

from .utils import (
    add_trace,
    add_unique_citations,
    best_snippet,
    build_chunk_map,
    chunks_as_citations,
    citations_for_ids,
    contains_any,
    dedupe,
    format_chunks_for_prompt,
    joined_uploaded_text,
    retrieve,
    uploaded_chunks,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an EU AI Act compliance analyst performing a first-pass document review.

Your task is to extract 12 specific facts about an AI use case from the provided document chunks.
Each chunk has a chunk_id you must reference when citing evidence.

For each fact, determine:
- "value": a clear, concise description (empty string "" if not present in the documents)
- "status":
  - "found" if the documents clearly and explicitly state this information
  - "uncertain" if the documents suggest or imply it but do not state it explicitly
  - "missing" if the documents contain no relevant information for this fact
- "chunk_ids": list of chunk_ids from the provided context that support this fact (empty list if missing)

Also write a "summary": 2-3 sentence plain-language overview of the AI use case based solely on the documents.

Respond with valid JSON only. No markdown. No text outside the JSON object.\
"""


@dataclass
class DocumentFactAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        model = settings.document_fact_agent_model
        if model:
            try:
                return self._run_llm(state, model)
            except Exception as exc:
                logger.warning(
                    "DocumentFactAgent LLM call failed (%s); falling back to heuristic.", exc
                )
        return self._run_heuristic(state)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _run_llm(self, state: AgentState, model: str) -> AgentState:
        chunks = uploaded_chunks(state, repo=self.repo)
        if not chunks:
            return self._run_heuristic(state)

        citations = chunks_as_citations(chunks)
        add_unique_citations(state, citations)
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
        state.summary = data.get("summary") or ""
        missing = [fact.label for fact in facts if fact.status == "missing"]
        state.missing_information = dedupe([*state.missing_information, *missing])

        found_count = sum(1 for f in facts if f.status == "found")
        add_trace(
            state,
            "DocumentFactAgent",
            "extract_facts",
            f"LLM extracted {found_count} facts and marked {len(missing)} missing.",
        )
        return state

    # ------------------------------------------------------------------
    # Heuristic fallback (original implementation)
    # ------------------------------------------------------------------

    def _run_heuristic(self, state: AgentState) -> AgentState:
        text = joined_uploaded_text(state, repo=self.repo)
        facts: list[ExtractedFact] = []

        for index, label in enumerate(REQUIRED_FACT_LABELS, start=1):
            fact = self._extract_fact(index, label, text, state)
            facts.append(fact)

        state.facts = facts
        state.summary = self._build_summary(facts)
        missing = [fact.label for fact in facts if fact.status == "missing"]
        state.missing_information = dedupe([*state.missing_information, *missing])
        add_trace(
            state,
            "DocumentFactAgent",
            "extract_facts",
            f"Extracted {sum(fact.status == 'found' for fact in facts)} facts and marked {len(missing)} missing.",
        )
        return state

    def _extract_fact(
        self,
        index: int,
        label: FactLabel,
        text: str,
        state: AgentState,
    ) -> ExtractedFact:
        spec = FACT_SPECS[label]
        query = spec["query"]
        citations = retrieve(
            state,
            query,
            source_types=["uploaded_document"],
            limit=2,
            repo=self.repo,
        )
        found_by_keyword = contains_any(text, spec["keywords"])

        if not citations and not found_by_keyword:
            return ExtractedFact(
                id=f"fact_{index}",
                label=label,
                value="",
                status="missing",
                citations=[],
            )

        if citations:
            value = spec["value_prefix"] + best_snippet(citations)
            status = "found" if found_by_keyword else "uncertain"
        else:
            value = spec["fallback"]
            status = "uncertain"

        return ExtractedFact(
            id=f"fact_{index}",
            label=label,
            value=value,
            status=status,
            citations=citations,
        )

    def _build_summary(self, facts: list[ExtractedFact]) -> str:
        found = {fact.label: fact for fact in facts if fact.status in {"found", "uncertain"}}
        purpose = found.get("Purpose")
        sector = found.get("Sector")
        impact = found.get("Potential impact on people")

        parts: list[str] = []
        if purpose and purpose.value:
            parts.append(purpose.value)
        if sector and sector.value:
            parts.append(sector.value)
        if impact and impact.value:
            parts.append(impact.value)
        if not parts:
            return "The uploaded documents do not yet provide enough information for a useful use-case summary."
        return " ".join(parts)


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

FACT_SPECS: dict[FactLabel, dict[str, object]] = {
    "Purpose": {
        "query": "purpose intended use objective use case",
        "keywords": ["purpose", "intended", "objective", "use case", "used to", "designed to"],
        "value_prefix": "Likely purpose: ",
        "fallback": "The use-case purpose is suggested but not explicit in the uploaded documents.",
    },
    "Users": {
        "query": "users operators deployers recruiters employees customers",
        "keywords": ["user", "operator", "deployer", "recruiter", "employee", "customer", "staff"],
        "value_prefix": "Possible users: ",
        "fallback": "The users are suggested but not explicit in the uploaded documents.",
    },
    "Affected persons": {
        "query": "affected persons candidates students customers citizens employees",
        "keywords": ["candidate", "student", "customer", "citizen", "employee", "affected person", "worker"],
        "value_prefix": "Potential affected persons: ",
        "fallback": "Affected persons are suggested but not explicit in the uploaded documents.",
    },
    "Sector": {
        "query": "sector employment education healthcare finance public service law enforcement",
        "keywords": ["employment", "hiring", "education", "health", "finance", "public service", "law enforcement"],
        "value_prefix": "Relevant sector signal: ",
        "fallback": "The sector is suggested but not explicit in the uploaded documents.",
    },
    "Input data": {
        "query": "input data personal data CV application biometric user prompt",
        "keywords": ["input", "data", "cv", "resume", "application", "biometric", "personal data", "prompt"],
        "value_prefix": "Input data signal: ",
        "fallback": "Input data is suggested but not explicit in the uploaded documents.",
    },
    "Outputs": {
        "query": "outputs predictions recommendations decisions scores ranking content",
        "keywords": ["output", "prediction", "recommendation", "decision", "score", "rank", "content", "summary"],
        "value_prefix": "Output signal: ",
        "fallback": "Outputs are suggested but not explicit in the uploaded documents.",
    },
    "Automation level": {
        "query": "automation autonomous automated human review decision support",
        "keywords": ["automated", "automation", "autonomous", "human review", "decision support"],
        "value_prefix": "Automation signal: ",
        "fallback": "Automation level is suggested but not explicit in the uploaded documents.",
    },
    "Human oversight": {
        "query": "human oversight human review approval monitoring recruiter review",
        "keywords": ["human oversight", "human review", "approval", "monitoring", "recruiter review", "reviewed by"],
        "value_prefix": "Human oversight signal: ",
        "fallback": "Human oversight is suggested but not explicit in the uploaded documents.",
    },
    "Deployment context": {
        "query": "deployment context deployed internal production EU workplace school",
        "keywords": ["deploy", "deployment", "production", "internal", "workplace", "school", "EU"],
        "value_prefix": "Deployment context signal: ",
        "fallback": "Deployment context is suggested but not explicit in the uploaded documents.",
    },
    "Use of AI-generated content": {
        "query": "AI-generated content synthetic text image audio video summary chatbot",
        "keywords": ["generated content", "synthetic", "chatbot", "summary", "image", "audio", "video", "text generation"],
        "value_prefix": "AI-generated content signal: ",
        "fallback": "AI-generated content use is suggested but not explicit in the uploaded documents.",
    },
    "Use of GPAI/LLM": {
        "query": "GPAI general-purpose AI LLM language model foundation model ChatGPT Claude",
        "keywords": ["GPAI", "general-purpose", "LLM", "language model", "foundation model", "ChatGPT", "Claude"],
        "value_prefix": "GPAI/LLM signal: ",
        "fallback": "GPAI or LLM use is suggested but not explicit in the uploaded documents.",
    },
    "Potential impact on people": {
        "query": "impact on people rights access employment benefits decisions significant effect",
        "keywords": ["impact", "rights", "access", "employment", "benefit", "decision", "candidate", "student", "customer"],
        "value_prefix": "Potential impact signal: ",
        "fallback": "Potential impact on people is suggested but not explicit in the uploaded documents.",
    },
}
