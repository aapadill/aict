from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.models.analysis import AgentState, AssessmentSection
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

REQUIRED_OBLIGATION_FACTS = ("Purpose", "Outputs", "Deployment context")

TRANSPARENCY_SIGNAL_KEYWORDS = (
    "chatbot",
    "interacts with",
    "interacts with users",
    "conversational",
    "generated content",
    "ai-generated",
    "synthetic",
    "deep fake",
    "summary",
    "summarizes",
)

GPAI_SIGNAL_KEYWORDS = (
    "GPAI",
    "general-purpose",
    "LLM",
    "language model",
    "foundation model",
    "ChatGPT",
    "Claude",
)

_SYSTEM_PROMPT = """\
You are an EU AI Act obligations mapping expert.

Based on the risk classification and extracted facts provided, identify the applicable EU AI Act
obligations and governance gaps for this AI use case.

Cover these categories as obligations sections:
1. Provider vs deployer roles — who develops and who deploys determines which obligations apply.
   Providers (Article 16): technical documentation, conformity assessment, registration, CE marking, post-market monitoring.
   Deployers (Article 26): fundamental rights impact assessment (where applicable), human oversight, logging, transparency to affected persons.
2. Transparency and labelling — Article 50 chatbot disclosure, emotion-recognition disclosure, AI-generated content labelling.
3. GPAI and LLM obligations — if a general-purpose AI model is used: technical documentation (Article 53),
   training data summary, copyright policy, systemic-risk assessment if applicable (Article 55).

Cover these categories as governance observation sections:
1. Documentation and accountability — technical file, purpose statement, data governance, role clarity.
2. Human oversight, monitoring, and logging — operational controls, override authority, post-deployment monitoring, incident reporting.

Cite uploaded-document chunks for use-case facts and regulatory chunks for legal rules. Do not
map obligations from legal chunks alone. Set confidence to "low" where the uploaded documents
do not confirm the relevant facts.
Keep the output concise and user-facing: prefer short conclusions, short reasoning, and avoid repeating the same uncertainty across sections.

Respond with valid JSON only. No markdown. No text outside the JSON object.\
"""

_USER_TEMPLATE = """\
Extracted facts:
{FACTS}

Risk classification:
{RISK}

Source chunks:
{CHUNKS}

Map the applicable obligations and governance gaps for this use case.
Return no more than 4 obligation sections, no more than 3 governance observations, and no more than 6 follow-up questions.

Return ONLY this JSON:
{
  "obligations": [
    {
      "title": "section title",
      "conclusion": "one short, plain-language conclusion",
      "confidence": "low|medium|high",
      "reasoning": "1-2 short sentences",
      "uncertainties": ["open questions, max 2"],
      "assumptions": ["assumptions made, max 2"],
      "chunk_ids": ["supporting chunk_ids"]
    }
  ],
  "governance_observations": [
    {
      "title": "section title",
      "conclusion": "one short, plain-language conclusion",
      "confidence": "low|medium|high",
      "reasoning": "1-2 short sentences",
      "uncertainties": ["open questions, max 2"],
      "assumptions": [],
      "chunk_ids": ["supporting chunk_ids"]
    }
  ],
  "follow_up_questions": ["list of prioritised follow-up questions"]
}\
"""


@dataclass
class ObligationsGovernanceAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        missing_facts = _missing_obligation_facts(state)
        if missing_facts:
            return self._run_unclear_guardrail(
                state,
                missing_facts,
                "core_uploaded_facts_missing",
            )

        model = settings.obligations_agent_model
        if not model:
            raise RuntimeError("OBLIGATIONS_AGENT_MODEL is required.")
        return self._run_llm(state, model)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _run_llm(self, state: AgentState, model: str) -> AgentState:
        missing_facts = _missing_obligation_facts(state)
        if missing_facts:
            return self._run_unclear_guardrail(
                state,
                missing_facts,
                "core_uploaded_facts_missing",
            )

        regulatory = retrieve(
            state,
            "provider deployer obligations documentation risk management human oversight transparency GPAI Article 16 26 50 53",
            source_types=["legislation", "official_guidance"],
            limit=8,
            repo=self.repo,
        )
        uploaded = retrieve(
            state,
            "provider deployer vendor operator roles responsibilities oversight logging",
            source_types=["uploaded_document"],
            limit=4,
            repo=self.repo,
        )
        all_citations = [*uploaded, *regulatory]
        chunk_map = build_chunk_map(all_citations)

        facts_summary = _format_facts(state)
        risk_summary = _format_risk(state)

        user_prompt = (
            _USER_TEMPLATE
            .replace("{FACTS}", facts_summary)
            .replace("{RISK}", risk_summary)
            .replace("{CHUNKS}", format_chunks_for_prompt(all_citations))
        )
        raw = llm_service.complete(
            model, _SYSTEM_PROMPT, user_prompt, json_mode=True, max_tokens=3500
        )
        data = llm_service.parse_json(raw)

        obligations = [
            _section_from_data(s, chunk_map) for s in data.get("obligations", [])[:4]
        ]
        governance_observations = [
            _section_from_data(s, chunk_map) for s in data.get("governance_observations", [])[:3]
        ]
        state.obligations = _apply_obligation_section_guardrails(
            state,
            obligations,
            repo=self.repo,
        )
        state.governance_observations = _apply_governance_section_guardrails(
            governance_observations
        )
        state.follow_up_questions = dedupe(
            [*state.follow_up_questions, *data.get("follow_up_questions", [])[:6]]
        )

        add_trace(
            state,
            "ObligationsGovernanceAgent",
            "map_obligations_and_governance",
            f"Produced {len(state.obligations)} obligation sections and "
            f"{len(state.governance_observations)} governance observations.",
        )
        return state

    def _run_unclear_guardrail(
        self,
        state: AgentState,
        missing_facts: list[str],
        reason: str,
    ) -> AgentState:
        state.obligations = [
            _unclear_obligations_section(
                [
                    "Obligation mapping requires uploaded-document evidence for: "
                    + ", ".join(missing_facts)
                    + ".",
                    "Legal corpus provisions were not applied because the uploaded documents do not establish the required use-case facts.",
                ]
            )
        ]
        state.governance_observations = [
            _intake_governance_section(
                [
                    "Upload a purpose statement, output description, deployment context, role information, and oversight details before mapping obligations.",
                ]
            )
        ]
        state.follow_up_questions = dedupe(
            [
                *state.follow_up_questions,
                "What is the system intended to do?",
                "What outputs does it produce and who acts on them?",
                "Where will the system be deployed and by whom?",
            ]
        )
        add_trace(
            state,
            "ObligationsGovernanceAgent",
            "map_obligations_and_governance",
            f"Guardrail withheld obligations mapping ({reason}): missing {', '.join(missing_facts)}.",
        )
        return state

def _format_facts(state: AgentState) -> str:
    if not state.facts:
        return "(no facts extracted yet)"
    lines = []
    for fact in state.facts:
        lines.append(f"- {fact.label} [{fact.status}]: {fact.value or '(not found)'}")
    return "\n".join(lines)


def _format_risk(state: AgentState) -> str:
    if state.risk_classification is None:
        return "(risk classification not yet available)"
    rc = state.risk_classification
    return f"Conclusion: {rc.conclusion}\nConfidence: {rc.confidence}\nReasoning: {rc.reasoning}"


def _section_from_data(data: dict, chunk_map: dict) -> AssessmentSection:
    confidence = data.get("confidence", "low")
    if confidence not in ("low", "medium", "high"):
        confidence = "low"
    return AssessmentSection(
        title=data.get("title", ""),
        conclusion=data.get("conclusion", ""),
        confidence=confidence,
        reasoning=data.get("reasoning", ""),
        citations=citations_for_ids(data.get("chunk_ids", []), chunk_map),
        assumptions=dedupe(data.get("assumptions", []))[:2],
        uncertainties=dedupe(data.get("uncertainties", []))[:2],
    )


def _missing_obligation_facts(state: AgentState) -> list[str]:
    facts = {fact.label: fact for fact in state.facts}
    missing: list[str] = []
    for label in REQUIRED_OBLIGATION_FACTS:
        fact = facts.get(label)
        if fact is None or fact.status == "missing" or not fact.citations:
            missing.append(label)
    return missing


def _unclear_obligations_section(uncertainties: list[str]) -> AssessmentSection:
    return AssessmentSection(
        title="Obligations",
        conclusion="Obligations cannot be mapped from the uploaded documents yet.",
        confidence="low",
        reasoning=(
            "The uploaded documents do not establish enough use-case facts to connect the system "
            "to provider, deployer, transparency, GPAI, or high-risk obligations."
        ),
        citations=[],
        assumptions=["Assessment is based only on uploaded documents and built-in AI Act corpus."],
        uncertainties=dedupe(uncertainties),
    )


def _intake_governance_section(uncertainties: list[str]) -> AssessmentSection:
    return AssessmentSection(
        title="Governance intake",
        conclusion="Collect basic system evidence before relying on governance recommendations.",
        confidence="low",
        reasoning=(
            "Governance observations require a grounded purpose, outputs, deployment context, "
            "roles, and controls. Legal reference material alone cannot establish those facts."
        ),
        citations=[],
        assumptions=[],
        uncertainties=dedupe(uncertainties),
    )


def _apply_obligation_section_guardrails(
    state: AgentState,
    sections: list[AssessmentSection],
    repo: JsonRepository,
) -> list[AssessmentSection]:
    uploaded_text = joined_uploaded_text(state, repo=repo)
    guarded: list[AssessmentSection] = []

    for section in sections:
        section_text = f"{section.title} {section.conclusion} {section.reasoning}".lower()
        if any(
            term in section_text
            for term in ("article 50", "transparency", "labelling", "labeling", "chatbot", "deep fake", "synthetic content")
        ) and not contains_any(
            uploaded_text,
            TRANSPARENCY_SIGNAL_KEYWORDS,
        ):
            guarded.append(_transparency_not_established_section())
            continue

        if (
            "gpai" in section_text
            or "llm" in section_text
            or "article 53" in section_text
            or "general-purpose" in section_text
            or "general purpose" in section_text
            or "foundation model" in section_text
        ) and not contains_any(uploaded_text, GPAI_SIGNAL_KEYWORDS):
            guarded.append(_gpai_not_established_section())
            continue

        if _has_legal_only_citations(section):
            guarded.append(_ungrounded_obligation_section(section))
            continue

        guarded.append(section)

    return _dedupe_sections(guarded)


def _apply_governance_section_guardrails(
    sections: list[AssessmentSection],
) -> list[AssessmentSection]:
    guarded: list[AssessmentSection] = []
    for section in sections:
        if _has_legal_only_citations(section):
            guarded.append(_ungrounded_governance_section(section))
        else:
            guarded.append(section)
    return _dedupe_sections(guarded)


def _transparency_not_established_section() -> AssessmentSection:
    return AssessmentSection(
        title="Transparency and labelling",
        conclusion="Transparency or labelling obligations are not established yet.",
        confidence="low",
        reasoning=(
            "The uploaded material does not clearly describe direct interaction with natural "
            "persons or AI-generated content disclosure needs."
        ),
        citations=[],
        assumptions=[],
        uncertainties=["Confirm whether the system interacts directly with natural persons or generates synthetic content."],
    )


def _gpai_not_established_section() -> AssessmentSection:
    return AssessmentSection(
        title="GPAI obligations",
        conclusion="GPAI obligations are not established from the uploaded documents.",
        confidence="low",
        reasoning="The uploaded material does not clearly identify a general-purpose AI model or LLM component.",
        citations=[],
        assumptions=[],
        uncertainties=["Ask whether any third-party GPAI or LLM component is used."],
    )


def _ungrounded_obligation_section(section: AssessmentSection) -> AssessmentSection:
    return AssessmentSection(
        title=section.title or "Obligation",
        conclusion="This obligation cannot be applied from the uploaded documents yet.",
        confidence="low",
        reasoning=(
            "The section referenced legal material, but no uploaded-document evidence established "
            "the factual trigger for applying that obligation."
        ),
        citations=[],
        assumptions=[],
        uncertainties=dedupe(
            [
                *section.uncertainties,
                "Upload source evidence for the use-case trigger before applying this obligation.",
            ]
        ),
    )


def _ungrounded_governance_section(section: AssessmentSection) -> AssessmentSection:
    return AssessmentSection(
        title=section.title or "Governance observation",
        conclusion="This governance observation needs uploaded-document support.",
        confidence="low",
        reasoning=(
            "The section referenced legal material, but no uploaded-document evidence established "
            "the system facts needed for this observation."
        ),
        citations=[],
        assumptions=[],
        uncertainties=dedupe(
            [
                *section.uncertainties,
                "Upload source evidence for this governance control or gap.",
            ]
        ),
    )


def _has_legal_only_citations(section: AssessmentSection) -> bool:
    return bool(section.citations) and not any(
        citation.source_type == "uploaded_document" for citation in section.citations
    )


def _dedupe_sections(sections: list[AssessmentSection]) -> list[AssessmentSection]:
    seen: set[str] = set()
    result: list[AssessmentSection] = []
    for section in sections:
        key = section.title.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(section)
    return result
