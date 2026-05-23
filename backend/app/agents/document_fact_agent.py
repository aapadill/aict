from __future__ import annotations

from dataclasses import dataclass

from app.models.analysis import AgentState, ExtractedFact, FactLabel, REQUIRED_FACT_LABELS
from app.storage import JsonRepository, repository

from .utils import add_trace, best_snippet, contains_any, dedupe, joined_uploaded_text, retrieve


@dataclass
class DocumentFactAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
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
