from __future__ import annotations

from dataclasses import dataclass

from app.models.analysis import AgentState, AssessmentSection
from app.storage import JsonRepository, repository

from .utils import add_trace, contains_any, dedupe, joined_uploaded_text, retrieve


@dataclass
class AISystemDefinitionAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        uploaded_text = joined_uploaded_text(state, repo=self.repo)
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

        ai_signals = contains_any(
            uploaded_text,
            [
                "AI",
                "machine learning",
                "model",
                "algorithm",
                "automated",
                "prediction",
                "recommendation",
                "decision",
                "ranking",
                "score",
                "LLM",
                "language model",
            ],
        )

        if ai_signals:
            conclusion = "The uploaded material appears to describe an AI system for first-pass AI Act analysis."
            confidence = "medium" if citations else "low"
            reasoning = (
                "The use case contains signals of automated inference or model-based outputs, "
                "and retrieved AI Act reference material describes AI systems in terms of machine-based "
                "systems producing predictions, content, recommendations, or decisions."
            )
            uncertainties = ["Confirm the exact technical architecture and level of autonomy."]
        else:
            conclusion = "The uploaded material does not yet clearly establish that the technology is an AI system."
            confidence = "low"
            reasoning = (
                "The documents do not provide enough technical detail to confirm machine-based inference, "
                "autonomy, adaptiveness, or AI-generated outputs."
            )
            uncertainties = [
                "Need technical description of model logic, autonomy, inputs, and outputs.",
            ]

        state.ai_system_assessment = AssessmentSection(
            title="AI-system definition assessment",
            conclusion=conclusion,
            confidence=confidence,
            reasoning=reasoning,
            citations=citations,
            assumptions=["Assessment is based only on uploaded documents and built-in AI Act corpus."],
            uncertainties=dedupe(uncertainties),
        )
        add_trace(
            state,
            "AISystemDefinitionAgent",
            "assess_ai_system_definition",
            f"AI-system signals {'found' if ai_signals else 'not confirmed'} with {len(citations)} citations.",
        )
        return state
