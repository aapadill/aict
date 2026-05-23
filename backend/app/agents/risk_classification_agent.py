from __future__ import annotations

import logging
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
  "chunk_ids": ["chunk_ids from the provided context that ground the conclusion"]
}\
"""


@dataclass
class RiskClassificationAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
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

        state.risk_classification = AssessmentSection(
            title="Risk classification",
            conclusion=data.get("conclusion", ""),
            confidence=confidence,
            reasoning=data.get("reasoning", ""),
            citations=citations_for_ids(data.get("chunk_ids", []), chunk_map),
            assumptions=["Classification is preliminary and based on currently uploaded materials."],
            uncertainties=dedupe(data.get("uncertainties", []))[:3],
        )
        add_trace(
            state,
            "RiskClassificationAgent",
            "classify_risk",
            f"LLM risk conclusion: {data.get('conclusion', '')[:120]}",
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
                "The use case contains sector or purpose signals that map to AI Act high-risk areas, "
                "such as employment, education, essential services, biometrics, law enforcement, migration, "
                "critical infrastructure, or administration of justice."
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

        state.risk_classification = AssessmentSection(
            title="Risk classification",
            conclusion=conclusion,
            confidence=confidence,
            reasoning=reasoning,
            citations=_dedupe_citations(citations),
            assumptions=["Classification is preliminary and based on currently uploaded materials."],
            uncertainties=dedupe(uncertainties),
        )
        add_trace(
            state,
            "RiskClassificationAgent",
            "classify_risk",
            f"Produced preliminary risk conclusion: {conclusion}",
        )
        return state

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


def _dedupe_citations(citations: list) -> list:
    seen: set[str] = set()
    result: list = []
    for citation in citations:
        if citation.id in seen:
            continue
        seen.add(citation.id)
        result.append(citation)
    return result
