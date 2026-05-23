from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.models.analysis import AgentState, AssessmentSection, Citation
from app.services import llm as llm_service
from app.storage import JsonRepository, repository

from .utils import (
    add_trace,
    build_chunk_map,
    citations_for_ids,
    contains_any,
    dedupe,
    format_chunks_for_prompt,
    joined_uploaded_text,
    retrieve,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an EU AI Act compliance analyst assessing whether a described use case involves an AI system.

Under EU AI Act Article 3(1), an AI system is: "a machine-based system that is designed to operate \
with varying levels of autonomy and that may exhibit adaptiveness after deployment, and that, for \
explicit or implicit objectives, infers, from the input it receives, how to generate outputs such as \
predictions, content, recommendations, or decisions that can influence physical or virtual environments."

Key assessment questions:
1. Does the system produce predictions, content, recommendations, or decisions?
2. Does it operate with some level of autonomy (versus purely rule-based deterministic logic)?
3. Is it machine-based?
4. Does it influence physical or virtual environments?

Be precise: rule-based expert systems may not qualify; machine-learning or neural-network-based \
systems typically do.

Legal corpus chunks describe the law. They do not prove that the user's uploaded use case has
AI-system characteristics. Uploaded-document chunks prove use-case facts. Legal-rule chunks prove
Article 3(1) criteria.

If uploaded-document chunks do not establish AI-system facts such as purpose, outputs, automation,
model use, or inference, return an unclear low-confidence assessment. Do not cite legal chunks just
to say the use case is not described.

Respond with valid JSON only. No markdown. No text outside the JSON object.\
"""

_USER_TEMPLATE = """\
Source chunks:
{CHUNKS}

Assess whether the described use case involves an AI system in scope of the EU AI Act Article 3(1).

Return ONLY this JSON:
{
  "conclusion": "one short, plain-language conclusion",
  "confidence": "low|medium|high",
  "reasoning": "1-2 short sentences grounded in the provided chunks",
  "uncertainties": ["only the most important remaining open questions, max 3"],
  "use_case_fact_chunk_ids": ["uploaded_document chunk_ids that establish the technical use-case facts"],
  "legal_rule_chunk_ids": ["legislation or official_guidance chunk_ids that establish Article 3(1) criteria"],
  "unsupported_claims": ["AI-system claims that could not be grounded in uploaded-document chunks"]
}\
"""

AI_SYSTEM_SIGNAL_FACT_LABELS = ("Purpose", "Outputs", "Automation level", "Use of GPAI/LLM")
AI_SYSTEM_SIGNAL_KEYWORDS = (
    "AI",
    "machine learning",
    "model",
    "algorithm",
    "automated",
    "automation",
    "prediction",
    "recommendation",
    "decision",
    "ranking",
    "score",
    "LLM",
    "language model",
    "generates",
    "summarizes",
)


@dataclass
class AISystemDefinitionAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        missing_evidence = _missing_ai_system_evidence(state, self.repo)
        if missing_evidence:
            return self._run_unclear_guardrail(state, missing_evidence)

        model = settings.ai_system_agent_model
        if model:
            try:
                return self._run_llm(state, model)
            except Exception as exc:
                logger.warning(
                    "AISystemDefinitionAgent LLM call failed (%s); falling back to heuristic.", exc
                )
        return self._run_heuristic(state)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _run_llm(self, state: AgentState, model: str) -> AgentState:
        uploaded = retrieve(
            state,
            "AI system model algorithm automated prediction recommendation decision",
            source_types=["uploaded_document"],
            limit=5,
            repo=self.repo,
        )
        regulatory = retrieve(
            state,
            "AI system definition Article 3 machine-based autonomy adaptiveness inference outputs",
            source_types=["legislation", "official_guidance"],
            limit=5,
            repo=self.repo,
        )
        all_citations = [*uploaded, *regulatory]
        chunk_map = build_chunk_map(all_citations)

        user_prompt = _USER_TEMPLATE.replace("{CHUNKS}", format_chunks_for_prompt(all_citations))
        raw = llm_service.complete(
            model, _SYSTEM_PROMPT, user_prompt, json_mode=True, max_tokens=1500
        )
        data = llm_service.parse_json(raw)

        confidence = data.get("confidence", "low")
        if confidence not in ("low", "medium", "high"):
            confidence = "low"

        use_case_citations = _citations_for_source_type(
            data.get("use_case_fact_chunk_ids") or data.get("chunk_ids", []),
            chunk_map,
            source_type="uploaded_document",
        )
        legal_citations = _citations_excluding_source_type(
            data.get("legal_rule_chunk_ids") or data.get("chunk_ids", []),
            chunk_map,
            excluded_source_type="uploaded_document",
        )
        unsupported_claims = _string_list(data.get("unsupported_claims", []))

        section = AssessmentSection(
            title="AI-system definition assessment",
            conclusion=data.get("conclusion", ""),
            confidence=confidence,
            reasoning=data.get("reasoning", ""),
            citations=_dedupe_citations([*use_case_citations, *legal_citations]),
            assumptions=["Assessment is based only on uploaded documents and built-in AI Act corpus."],
            uncertainties=dedupe(
                [
                    *_string_list(data.get("uncertainties", []))[:3],
                    *[f"Unsupported AI-system claim: {claim}" for claim in unsupported_claims],
                ]
            ),
        )
        state.ai_system_assessment = self._apply_definition_guardrails(
            state,
            section,
            use_case_citations=use_case_citations,
            legal_citations=legal_citations,
        )
        add_trace(
            state,
            "AISystemDefinitionAgent",
            "assess_ai_system_definition",
            f"Assessed AI-system scope after guardrails: {state.ai_system_assessment.conclusion[:120]}",
        )
        return state

    # ------------------------------------------------------------------
    # Heuristic fallback (original implementation)
    # ------------------------------------------------------------------

    def _run_heuristic(self, state: AgentState) -> AgentState:
        uploaded_text = joined_uploaded_text(state, repo=self.repo)
        ai_signals = contains_any(
            uploaded_text,
            AI_SYSTEM_SIGNAL_KEYWORDS,
        )

        if ai_signals:
            regulatory_citations = retrieve(
                state,
                "AI system machine-based autonomy adaptiveness predictions recommendations decisions Article 3",
                source_types=["legislation", "official_guidance"],
                limit=3,
                repo=self.repo,
            )
            fact_citations = retrieve(
                state,
                "automated predictions recommendations decisions outputs AI system",
                source_types=["uploaded_document"],
                limit=2,
                repo=self.repo,
            )
            citations = [*fact_citations, *regulatory_citations]
            conclusion = "The uploaded material appears to describe an AI system for first-pass AI Act analysis."
            confidence = "medium" if citations else "low"
            reasoning = (
                "The use case contains signals of automated inference or model-based outputs, "
                "and retrieved AI Act reference material describes AI systems in terms of machine-based "
                "systems producing predictions, content, recommendations, or decisions."
            )
            uncertainties = ["Confirm the exact technical architecture and level of autonomy."]
        else:
            state.ai_system_assessment = _unclear_definition_section(
                [
                    "Uploaded documents do not establish AI-system technical facts such as model use, automation, inference, or outputs.",
                    "Legal corpus definitions were not cited because they do not describe the uploaded use case.",
                ]
            )
            add_trace(
                state,
                "AISystemDefinitionAgent",
                "assess_ai_system_definition",
                "Guardrail forced unclear AI-system assessment: no uploaded AI-system signal.",
            )
            return state

        section = AssessmentSection(
            title="AI-system definition assessment",
            conclusion=conclusion,
            confidence=confidence,
            reasoning=reasoning,
            citations=citations,
            assumptions=["Assessment is based only on uploaded documents and built-in AI Act corpus."],
            uncertainties=dedupe(uncertainties),
        )
        state.ai_system_assessment = self._apply_definition_guardrails(
            state,
            section,
            use_case_citations=[
                citation for citation in section.citations if citation.source_type == "uploaded_document"
            ],
            legal_citations=[
                citation for citation in section.citations if citation.source_type != "uploaded_document"
            ],
        )
        add_trace(
            state,
            "AISystemDefinitionAgent",
            "assess_ai_system_definition",
            f"AI-system signals found; conclusion after guardrails: {state.ai_system_assessment.conclusion}",
        )
        return state

    def _run_unclear_guardrail(
        self,
        state: AgentState,
        missing_evidence: list[str],
    ) -> AgentState:
        state.ai_system_assessment = _unclear_definition_section(
            [
                "AI-system definition assessment requires uploaded-document evidence for: "
                + ", ".join(missing_evidence)
                + ".",
                "Legal corpus definitions were not cited because they do not describe the uploaded use case.",
            ]
        )
        add_trace(
            state,
            "AISystemDefinitionAgent",
            "assess_ai_system_definition",
            f"Guardrail forced unclear AI-system assessment: missing {', '.join(missing_evidence)}.",
        )
        return state

    def _apply_definition_guardrails(
        self,
        state: AgentState,
        section: AssessmentSection,
        use_case_citations: list[Citation],
        legal_citations: list[Citation],
    ) -> AssessmentSection:
        missing_evidence = _missing_ai_system_evidence(state, self.repo)
        if missing_evidence:
            return _unclear_definition_section(
                [
                    "AI-system definition assessment requires uploaded-document evidence for: "
                    + ", ".join(missing_evidence)
                    + ".",
                    "Legal corpus definitions were not cited because they do not describe the uploaded use case.",
                ]
            )

        if _is_determinate_definition(section) and (not use_case_citations or not legal_citations):
            return _unclear_definition_section(
                [
                    "A determinate AI-system definition assessment requires both uploaded-document fact evidence and Article 3(1) legal-rule evidence.",
                    "The model output did not provide both evidence types, so the assessment was downgraded.",
                ]
            )

        return section


def _missing_ai_system_evidence(state: AgentState, repo: JsonRepository) -> list[str]:
    facts = {fact.label: fact for fact in state.facts}
    text = joined_uploaded_text(state, repo=repo)
    missing: list[str] = []

    purpose = facts.get("Purpose")
    if not _fact_has_cited_evidence(purpose):
        missing.append("Purpose")

    output_or_automation = any(
        _fact_has_cited_evidence(facts.get(label))
        for label in ("Outputs", "Automation level", "Use of GPAI/LLM")
    )
    if not output_or_automation:
        missing.append("Outputs or automation/model-use signal")

    if not contains_any(text, AI_SYSTEM_SIGNAL_KEYWORDS):
        missing.append("AI-system technical signal")

    return missing


def _fact_has_cited_evidence(fact: object) -> bool:
    return bool(
        fact is not None
        and getattr(fact, "status", "missing") != "missing"
        and getattr(fact, "citations", [])
    )


def _unclear_definition_section(uncertainties: list[str]) -> AssessmentSection:
    return AssessmentSection(
        title="AI-system definition assessment",
        conclusion="The uploaded documents do not yet establish whether this is an AI system.",
        confidence="low",
        reasoning=(
            "The uploaded documents do not provide enough use-case or technical facts to assess "
            "Article 3(1) scope. Legal definitions alone cannot establish facts about the system."
        ),
        citations=[],
        assumptions=["Assessment is based only on uploaded documents and built-in AI Act corpus."],
        uncertainties=dedupe(uncertainties),
    )


def _is_determinate_definition(section: AssessmentSection) -> bool:
    text = f"{section.conclusion} {section.reasoning}".lower()
    if any(term in text for term in ("unclear", "insufficient", "cannot determine", "not enough", "not yet establish")):
        return False
    return any(
        term in text
        for term in (
            "is an ai system",
            "appears to describe an ai system",
            "in scope",
            "out of scope",
            "not an ai system",
            "does not qualify",
        )
    )


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    result: list[Citation] = []
    for citation in citations:
        key = citation.chunk_id or citation.id
        if key in seen:
            continue
        seen.add(key)
        result.append(citation)
    return result


def _citations_for_source_type(
    chunk_ids: list[str],
    chunk_map: dict[str, Citation],
    source_type: str,
) -> list[Citation]:
    return [
        citation
        for citation in citations_for_ids(_string_list(chunk_ids), chunk_map)
        if citation.source_type == source_type
    ]


def _citations_excluding_source_type(
    chunk_ids: list[str],
    chunk_map: dict[str, Citation],
    excluded_source_type: str,
) -> list[Citation]:
    return [
        citation
        for citation in citations_for_ids(_string_list(chunk_ids), chunk_map)
        if citation.source_type != excluded_source_type
    ]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
