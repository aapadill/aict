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
You are an EU AI Act risk classification expert.

Risk levels under the EU AI Act:

1. PROHIBITED (Article 5) — must not be placed on the market or used:
   - Subliminal, manipulative, or deceptive techniques that distort behaviour to harm people
   - Exploitation of vulnerabilities (age, disability, socioeconomic situation)
   - Social scoring by public authorities that leads to detrimental treatment
   - Real-time remote biometric identification in publicly accessible spaces by law enforcement (with limited exceptions)
   - Retrospective remote biometric identification (except for prosecution of serious crimes)
   - Emotion recognition in workplace or educational settings
   - Biometric categorisation that infers sensitive characteristics (race, political opinions, religion, etc.)
   - Individual criminal risk assessment used to predict reoffending based on profiling
   - Untargeted scraping of facial images to build databases

2. HIGH-RISK (Annex III) — permitted with conformity obligations:
   - Biometric identification and categorisation (excluding prohibited cases)
   - Critical infrastructure safety (transport, water, gas, heating, electricity, etc.)
   - Education and vocational training (access decisions, assessment, monitoring)
   - Employment, workers management, access to self-employment (CV scoring, task allocation, monitoring)
   - Essential private and public services (credit scoring, benefits eligibility, emergency dispatch)
   - Law enforcement (risk assessment of individuals, polygraphs, evaluation of evidence reliability)
   - Migration, asylum, and border control management
   - Administration of justice and democratic processes

3. LIMITED RISK (Article 50 transparency obligations):
   - Systems that interact directly with natural persons (chatbots) → must inform users
   - Emotion recognition systems → must inform affected persons
   - AI-generated or manipulated content (deep fakes, synthetic images/video/audio) → must be labelled
   - AI-generated text on matters of public interest → must be disclosed

4. MINIMAL RISK: All other AI systems (no specific obligations beyond general principles).

Important: prohibited-practice concerns take priority and must be flagged even if high-risk signals are also present.

Legal corpus chunks describe the law. They do not prove that the user's uploaded use case belongs to a category.
Uploaded-document chunks prove use-case facts. Legal-rule chunks prove AI Act rules.

If uploaded-document chunks do not clearly establish the intended purpose, outputs, sector, and deployment context,
return an unclear low-confidence classification. Do not infer categories from legal examples.

Respond with valid JSON only. No markdown. No text outside the JSON object.\
"""

_USER_TEMPLATE = """\
Source chunks:
{CHUNKS}

Classify the risk level of the AI use case described in the uploaded document chunks.

Return ONLY this JSON:
{
  "conclusion": "one short, plain-language risk classification conclusion",
  "confidence": "low|medium|high",
  "reasoning": "2-3 short sentences referencing specific Annex III categories or Article 5 provisions where applicable",
  "uncertainties": ["only open questions that could change the classification, max 3"],
  "use_case_fact_chunk_ids": ["uploaded_document chunk_ids that establish the use-case facts being classified"],
  "legal_rule_chunk_ids": ["legislation or official_guidance chunk_ids that establish the legal rule"],
  "unsupported_claims": ["classification claims that could not be grounded in uploaded-document chunks"]
}\
"""

REQUIRED_CLASSIFICATION_FACTS = ("Purpose", "Sector", "Outputs", "Deployment context")

CATEGORY_EVIDENCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "biometric": ("biometric", "face recognition", "facial recognition", "fingerprint", "identity verification"),
    "migration": ("migration", "asylum", "border control", "border"),
    "asylum": ("migration", "asylum", "border control", "border"),
    "border": ("migration", "asylum", "border control", "border"),
    "law enforcement": ("law enforcement", "policing", "police", "criminal offence"),
    "employment": ("employment", "hiring", "recruiting", "candidate", "worker management"),
    "education": ("education", "student", "school", "vocational"),
    "essential": ("essential service", "benefit", "credit", "loan", "insurance"),
    "critical infrastructure": ("critical infrastructure", "energy grid", "transport network"),
    "justice": ("court", "judge", "justice", "democratic process", "election"),
}


@dataclass
class RiskClassificationAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        missing_facts = _missing_classification_facts(state)
        if missing_facts:
            return self._run_unclear_guardrail(
                state,
                missing_facts,
                "core_uploaded_facts_missing",
            )

        model = settings.risk_classification_agent_model
        if model:
            try:
                return self._run_llm(state, model)
            except Exception as exc:
                logger.warning(
                    "RiskClassificationAgent LLM call failed (%s); falling back to heuristic.", exc
                )
        return self._run_heuristic(state)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _run_llm(self, state: AgentState, model: str) -> AgentState:
        uploaded = retrieve(
            state,
            "AI system purpose sector deployment affected persons outputs",
            source_types=["uploaded_document"],
            limit=5,
            repo=self.repo,
        )
        high_risk = retrieve(
            state,
            "Annex III high-risk employment education biometrics law enforcement migration infrastructure justice essential services",
            source_types=["legislation", "official_guidance"],
            limit=4,
            repo=self.repo,
        )
        prohibited = retrieve(
            state,
            "Article 5 prohibited manipulation social scoring biometric emotion recognition real-time remote",
            source_types=["legislation", "official_guidance"],
            limit=4,
            repo=self.repo,
        )
        limited_risk = retrieve(
            state,
            "Article 50 transparency chatbot generated content deep fake emotion recognition",
            source_types=["legislation", "official_guidance"],
            limit=3,
            repo=self.repo,
        )
        all_citations = [*uploaded, *high_risk, *prohibited, *limited_risk]
        chunk_map = build_chunk_map(all_citations)

        user_prompt = _USER_TEMPLATE.replace("{CHUNKS}", format_chunks_for_prompt(all_citations))
        raw = llm_service.complete(
            model, _SYSTEM_PROMPT, user_prompt, json_mode=True, max_tokens=2000
        )
        data = llm_service.parse_json(raw)

        confidence = data.get("confidence", "low")
        if confidence not in ("low", "medium", "high"):
            confidence = "low"

        use_case_citations = _citations_for_source_type(
            data.get("use_case_fact_chunk_ids", []),
            chunk_map,
            source_type="uploaded_document",
        )
        legal_citations = _citations_excluding_source_type(
            data.get("legal_rule_chunk_ids", []),
            chunk_map,
            excluded_source_type="uploaded_document",
        )
        unsupported_claims = _string_list(data.get("unsupported_claims", []))

        section = AssessmentSection(
            title="Risk classification",
            conclusion=data.get("conclusion", ""),
            confidence=confidence,
            reasoning=data.get("reasoning", ""),
            citations=_dedupe_citations([*use_case_citations, *legal_citations]),
            assumptions=["Classification is preliminary and based on currently uploaded materials."],
            uncertainties=dedupe(
                [
                    *_string_list(data.get("uncertainties", []))[:3],
                    *[f"Unsupported classification claim: {claim}" for claim in unsupported_claims],
                ]
            ),
        )
        state.risk_classification = self._apply_classification_guardrails(
            state,
            section,
            use_case_citations=use_case_citations,
            legal_citations=legal_citations,
        )
        add_trace(
            state,
            "RiskClassificationAgent",
            "classify_risk",
            f"Risk conclusion after guardrails: {state.risk_classification.conclusion[:120]}",
        )
        return state

    # ------------------------------------------------------------------
    # Heuristic fallback (original implementation)
    # ------------------------------------------------------------------

    def _run_heuristic(self, state: AgentState) -> AgentState:
        text = joined_uploaded_text(state, repo=self.repo)
        regulatory_citations = retrieve(
            state,
            "Annex III high-risk employment education essential services biometrics law enforcement",
            source_types=["legislation", "official_guidance"],
            limit=4,
            repo=self.repo,
        )
        prohibited_citations = retrieve(
            state,
            "Article 5 prohibited practices manipulation vulnerability social scoring biometric emotion recognition",
            source_types=["legislation", "official_guidance"],
            limit=3,
            repo=self.repo,
        )

        sector = self._sector_signal(text)
        prohibited = self._prohibited_signal(text)
        limited = self._limited_risk_signal(text)

        if prohibited:
            conclusion = f"Potential prohibited-practice issue: {prohibited}."
            confidence = "medium"
            reasoning = (
                "The uploaded material includes signals that overlap with prohibited-practice themes. "
                "This needs immediate expert review before assuming the use case can proceed."
            )
            citations = [*prohibited_citations, *retrieve(state, prohibited, ["uploaded_document"], 2, self.repo)]
            uncertainties = ["The exact intended purpose, safeguards, and exceptions must be confirmed."]
        elif sector:
            conclusion = f"Possible high-risk classification due to {sector} context."
            confidence = "medium"
            reasoning = (
                f"The uploaded material contains {sector} signals that may map to an AI Act high-risk area. "
                "The exact Annex III intended purpose and any applicable exception still need confirmation."
            )
            citations = [
                *retrieve(state, sector, ["uploaded_document"], 2, self.repo),
                *regulatory_citations,
            ]
            uncertainties = [
                "Confirm whether the system falls within an Annex III intended purpose or an applicable exception.",
            ]
        elif limited:
            conclusion = f"Possible limited-risk transparency case due to {limited}."
            confidence = "medium"
            reasoning = (
                "The use case appears to involve interaction with people or generated content, "
                "which can trigger transparency or labelling obligations even where high-risk classification is not established."
            )
            citations = [
                *retrieve(state, limited, ["uploaded_document"], 2, self.repo),
                *retrieve(state, "Article 50 transparency chatbot generated content deep fake", ["legislation", "official_guidance"], 3, self.repo),
            ]
            uncertainties = ["Confirm whether users or affected persons are clearly informed about AI use."]
        else:
            conclusion = "Risk classification is unclear from the uploaded documents."
            confidence = "low"
            reasoning = (
                "The documents do not clearly establish prohibited-practice, high-risk, or limited-risk triggers. "
                "A minimal-risk conclusion would be premature without more deployment details."
            )
            citations = regulatory_citations[:2]
            uncertainties = [
                "Need clearer sector, affected-person, output, and deployment-context facts.",
            ]

        section = AssessmentSection(
            title="Risk classification",
            conclusion=conclusion,
            confidence=confidence,
            reasoning=reasoning,
            citations=_dedupe_citations(citations),
            assumptions=["Classification is preliminary and based on currently uploaded materials."],
            uncertainties=dedupe(uncertainties),
        )
        state.risk_classification = self._apply_classification_guardrails(
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
            "RiskClassificationAgent",
            "classify_risk",
            f"Produced preliminary risk conclusion after guardrails: {state.risk_classification.conclusion}",
        )
        return state

    def _run_unclear_guardrail(
        self,
        state: AgentState,
        missing_facts: list[str],
        reason: str,
    ) -> AgentState:
        state.risk_classification = _unclear_classification_section(
            [
                "Risk classification requires uploaded-document evidence for: "
                + ", ".join(missing_facts)
                + ".",
                "Legal corpus examples were not applied because the uploaded documents do not establish the required use-case facts.",
            ]
        )
        add_trace(
            state,
            "RiskClassificationAgent",
            "classify_risk",
            f"Guardrail forced unclear classification ({reason}): missing {', '.join(missing_facts)}.",
        )
        return state

    def _apply_classification_guardrails(
        self,
        state: AgentState,
        section: AssessmentSection,
        use_case_citations: list[Citation],
        legal_citations: list[Citation],
    ) -> AssessmentSection:
        missing_facts = _missing_classification_facts(state)
        if missing_facts:
            return _unclear_classification_section(
                [
                    "Risk classification requires uploaded-document evidence for: "
                    + ", ".join(missing_facts)
                    + ".",
                    "Legal corpus examples were not applied because the uploaded documents do not establish the required use-case facts.",
                ]
            )

        if _is_determinate_classification(section) and (not use_case_citations or not legal_citations):
            return _unclear_classification_section(
                [
                    "A determinate risk classification requires both uploaded-document fact evidence and legal-rule evidence.",
                    "The model output did not provide both evidence types, so the classification was downgraded.",
                ]
            )

        unsupported_terms = _unsupported_category_terms(
            f"{section.conclusion} {section.reasoning}",
            joined_uploaded_text(state, repo=self.repo),
        )
        if unsupported_terms:
            return _unclear_classification_section(
                [
                    "The model mentioned category terms not supported by uploaded-document evidence: "
                    + ", ".join(unsupported_terms)
                    + ".",
                    "Legal examples cannot establish facts about the uploaded use case.",
                ]
            )

        return section

    def _prohibited_signal(self, text: str) -> str | None:
        signals = [
            ("manipulative or deceptive techniques", ["manipulative", "deceptive", "subliminal"]),
            ("exploitation of vulnerabilities", ["vulnerability", "age", "disability", "socioeconomic"]),
            ("social scoring", ["social scoring", "social score"]),
            ("emotion recognition in workplace or education", ["emotion recognition", "infer emotions"]),
            ("sensitive biometric categorisation", ["biometric categorisation", "sensitive characteristic"]),
            ("untargeted facial-image scraping", ["facial recognition database", "scraping facial"]),
        ]
        for label, keywords in signals:
            if contains_any(text, keywords):
                return label
        return None

    def _sector_signal(self, text: str) -> str | None:
        signals = [
            ("employment or worker-management", ["employment", "hiring", "recruiting", "candidate", "worker management"]),
            ("education or vocational training", ["education", "student", "school", "vocational"]),
            ("essential public or private services", ["essential service", "benefit", "credit", "loan", "insurance"]),
            ("biometrics", ["biometric", "face recognition", "fingerprint"]),
            ("law enforcement", ["law enforcement", "policing", "criminal offence"]),
            ("migration, asylum, or border control", ["migration", "asylum", "border control"]),
            ("critical infrastructure", ["critical infrastructure", "energy grid", "transport network"]),
            ("administration of justice or democratic processes", ["court", "judge", "democratic process", "election"]),
        ]
        for label, keywords in signals:
            if contains_any(text, keywords):
                return label
        return None

    def _limited_risk_signal(self, text: str) -> str | None:
        signals = [
            ("direct interaction with people", ["chatbot", "interacts with users", "conversational"]),
            ("AI-generated or synthetic content", ["generated content", "synthetic", "deep fake", "summarizes", "summary"]),
        ]
        for label, keywords in signals:
            if contains_any(text, keywords):
                return label
        return None


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


def _missing_classification_facts(state: AgentState) -> list[str]:
    facts = {fact.label: fact for fact in state.facts}
    missing: list[str] = []
    for label in REQUIRED_CLASSIFICATION_FACTS:
        fact = facts.get(label)
        if fact is None or fact.status != "found":
            missing.append(label)
    return missing


def _unclear_classification_section(uncertainties: list[str]) -> AssessmentSection:
    return AssessmentSection(
        title="Risk classification",
        conclusion="Risk classification is unclear from the uploaded documents.",
        confidence="low",
        reasoning=(
            "The uploaded documents do not establish enough use-case facts to classify the system as "
            "prohibited, high-risk, limited-risk, or minimal-risk. A legal category should not be inferred "
            "from AI Act corpus examples alone."
        ),
        citations=[],
        assumptions=["Classification is preliminary and based on currently uploaded materials."],
        uncertainties=dedupe(uncertainties),
    )


def _is_determinate_classification(section: AssessmentSection) -> bool:
    text = f"{section.conclusion} {section.reasoning}".lower()
    if any(term in text for term in ("unclear", "insufficient", "cannot determine", "not enough")):
        return False
    return any(term in text for term in ("high-risk", "high risk", "prohibited", "limited-risk", "minimal-risk", "minimal risk"))


def _unsupported_category_terms(text: str, uploaded_text: str) -> list[str]:
    unsupported: list[str] = []
    for term, evidence_keywords in CATEGORY_EVIDENCE_KEYWORDS.items():
        if term not in text.lower():
            continue
        if not contains_any(uploaded_text, evidence_keywords):
            unsupported.append(term)
    return unsupported


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
