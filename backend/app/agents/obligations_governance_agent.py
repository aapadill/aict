from __future__ import annotations

from dataclasses import dataclass

from app.models.analysis import AgentState, AssessmentSection
from app.storage import JsonRepository, repository

from .utils import add_trace, contains_any, dedupe, joined_uploaded_text, retrieve


@dataclass
class ObligationsGovernanceAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        text = joined_uploaded_text(state, repo=self.repo)
        role_section = self._role_and_obligation_section(state, text)
        transparency_section = self._transparency_section(state, text)
        gpai_section = self._gpai_section(state, text)

        state.obligations = [role_section, transparency_section, gpai_section]
        state.governance_observations = self._governance_sections(state, text)
        state.follow_up_questions = dedupe(
            [
                *state.follow_up_questions,
                "Who is the provider of the AI system or model?",
                "Who deploys the system and in which EU context?",
                "What human oversight, logging, monitoring, and appeal mechanisms exist?",
                "Does the system use a third-party GPAI or LLM component?",
            ]
        )
        add_trace(
            state,
            "ObligationsGovernanceAgent",
            "map_obligations_and_governance",
            f"Produced {len(state.obligations)} obligation sections and {len(state.governance_observations)} governance observations.",
        )
        return state

    def _role_and_obligation_section(self, state: AgentState, text: str) -> AssessmentSection:
        provider_signal = contains_any(text, ["develop", "provider", "vendor", "market", "sell", "supply"])
        deployer_signal = contains_any(text, ["use internally", "deployer", "operator", "recruiter", "customer uses"])
        uploaded_citations = retrieve(
            state,
            "provider deployer vendor operator user deploys system",
            source_types=["uploaded_document"],
            limit=2,
            repo=self.repo,
        )
        regulatory_citations = retrieve(
            state,
            "provider deployer obligations high-risk AI system documentation oversight",
            source_types=["legislation", "official_guidance"],
            limit=3,
            repo=self.repo,
        )

        roles: list[str] = []
        if provider_signal:
            roles.append("provider")
        if deployer_signal:
            roles.append("deployer")

        if roles:
            conclusion = f"Possible role(s): {', '.join(roles)}."
            confidence = "medium"
            reasoning = (
                "The uploaded documents include role signals, but role allocation should be confirmed by contracts, "
                "system ownership, and deployment responsibilities."
            )
        else:
            conclusion = "Provider/deployer roles are not clear from the uploaded documents."
            confidence = "low"
            reasoning = "The current source material does not clearly identify who develops, places on the market, or deploys the system."

        return AssessmentSection(
            title="Roles and obligations",
            conclusion=conclusion,
            confidence=confidence,
            reasoning=reasoning,
            citations=[*uploaded_citations, *regulatory_citations],
            assumptions=["Role mapping is preliminary until vendor, customer, and deployment responsibilities are confirmed."],
            uncertainties=["Provider/deployer responsibility chain may change the applicable obligations."],
        )

    def _transparency_section(self, state: AgentState, text: str) -> AssessmentSection:
        transparency_signal = contains_any(
            text,
            ["chatbot", "interacts with", "generated content", "synthetic", "deep fake", "summary", "summarizes"],
        )
        citations = [
            *retrieve(state, "chatbot generated content synthetic summary transparency", ["uploaded_document"], 2, self.repo),
            *retrieve(state, "Article 50 transparency obligations AI-generated content chatbot", ["legislation", "official_guidance"], 3, self.repo),
        ]

        if transparency_signal:
            conclusion = "Transparency or labelling obligations may be relevant."
            confidence = "medium"
            reasoning = "The uploaded material suggests user interaction or generated content that may need disclosure or labelling."
            uncertainties = ["Confirm exactly who sees the AI output and whether content is presented as AI-generated."]
        else:
            conclusion = "Transparency or labelling obligations are not established yet."
            confidence = "low"
            reasoning = "The uploaded material does not clearly describe direct user interaction or AI-generated content disclosure needs."
            uncertainties = ["Confirm whether the system interacts directly with natural persons or generates synthetic content."]

        return AssessmentSection(
            title="Transparency and labelling",
            conclusion=conclusion,
            confidence=confidence,
            reasoning=reasoning,
            citations=citations,
            assumptions=[],
            uncertainties=uncertainties,
        )

    def _gpai_section(self, state: AgentState, text: str) -> AssessmentSection:
        gpai_signal = contains_any(
            text,
            ["GPAI", "general-purpose", "LLM", "language model", "foundation model", "ChatGPT", "Claude"],
        )
        citations = [
            *retrieve(state, "GPAI LLM language model foundation model", ["uploaded_document"], 2, self.repo),
            *retrieve(state, "Article 53 general-purpose AI model obligations technical documentation training content summary", ["legislation", "official_guidance"], 3, self.repo),
        ]

        if gpai_signal:
            conclusion = "GPAI or LLM obligations may be relevant to the responsibility chain."
            confidence = "medium"
            reasoning = "The uploaded material suggests use of a general-purpose AI or language-model component."
            uncertainties = ["Confirm the model provider, integration pattern, and available compliance documentation."]
        else:
            conclusion = "GPAI obligations are not established from the uploaded documents."
            confidence = "low"
            reasoning = "The current material does not clearly identify a general-purpose AI model or LLM component."
            uncertainties = ["Ask whether any third-party GPAI or LLM component is used."]

        return AssessmentSection(
            title="GPAI obligations",
            conclusion=conclusion,
            confidence=confidence,
            reasoning=reasoning,
            citations=citations,
            assumptions=[],
            uncertainties=uncertainties,
        )

    def _governance_sections(self, state: AgentState, text: str) -> list[AssessmentSection]:
        governance_citations = retrieve(
            state,
            "documentation risk management logging monitoring human oversight accountability",
            source_types=["legislation", "official_guidance", "uploaded_document"],
            limit=5,
            repo=self.repo,
        )
        oversight_present = contains_any(text, ["human oversight", "human review", "reviewed by", "approval"])
        logging_present = contains_any(text, ["log", "audit", "monitoring", "trace"])

        return [
            AssessmentSection(
                title="Documentation and accountability",
                conclusion="Create or collect documentation for purpose, data, model behavior, roles, and decisions.",
                confidence="medium",
                reasoning="A first-pass AI Act review needs documented evidence for role clarity, intended purpose, risk classification, and obligations.",
                citations=governance_citations,
                assumptions=["Documentation needs depend on the final AI Act role and risk classification."],
                uncertainties=["Current uploaded documents may not be sufficient for a complete technical file or deployer record."],
            ),
            AssessmentSection(
                title="Human oversight, monitoring, and logging",
                conclusion=(
                    "Human oversight is mentioned and should be operationalized."
                    if oversight_present
                    else "Human oversight should be specified before relying on this assessment."
                ),
                confidence="medium" if oversight_present or logging_present else "low",
                reasoning=(
                    "Governance should cover practical controls such as review authority, escalation, monitoring, logging, and accountability."
                ),
                citations=governance_citations,
                assumptions=[],
                uncertainties=[
                    "Confirm who can override outputs, how logs are kept, and how post-deployment monitoring works."
                ],
            ),
        ]
