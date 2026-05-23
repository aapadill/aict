from __future__ import annotations

from dataclasses import dataclass

from app.models.analysis import AgentState, AssessmentSection
from app.storage import JsonRepository, repository

from .utils import add_trace, contains_any, dedupe, joined_uploaded_text, retrieve


@dataclass
class RiskClassificationAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
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
            citations=dedupe_citations(citations),
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


def dedupe_citations(citations: list) -> list:
    seen: set[str] = set()
    result: list = []
    for citation in citations:
        if citation.id in seen:
            continue
        seen.add(citation.id)
        result.append(citation)
    return result
