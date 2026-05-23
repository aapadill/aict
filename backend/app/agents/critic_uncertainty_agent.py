from __future__ import annotations

from dataclasses import dataclass

from app.models.analysis import AgentState, AssessmentSection, LIMITATION_NOTICE
from app.storage import JsonRepository, repository

from .utils import add_trace, dedupe, joined_uploaded_text

CRITICAL_FACT_LABELS = (
    "Purpose",
    "Sector",
    "Affected persons",
    "Input data",
    "Outputs",
    "Automation level",
    "Human oversight",
    "Deployment context",
)


@dataclass
class CriticUncertaintyAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        missing_labels = [
            fact.label
            for fact in state.facts
            if fact.label in CRITICAL_FACT_LABELS and fact.status != "found"
        ]
        weak_labels = [
            fact.label
            for fact in state.facts
            if fact.status == "found" and not fact.citations
        ]
        contradiction_notes = self._find_visible_contradictions(state)

        state.missing_information = dedupe(
            [
                *state.missing_information,
                *[f"Confirm {label}." for label in missing_labels],
                *[f"Add cited evidence for {label}." for label in weak_labels],
                *contradiction_notes,
            ]
        )
        state.uncertainties = dedupe(
            [
                *state.uncertainties,
                *[f"{label} is missing or uncertain and may affect classification." for label in missing_labels],
                *[f"{label} was inferred without strong citation support." for label in weak_labels],
                *contradiction_notes,
            ]
        )
        state.follow_up_questions = dedupe(
            [
                *state.follow_up_questions,
                *self._questions_for_missing(missing_labels),
                *self._questions_for_weak_evidence(weak_labels),
                *(
                    ["Which uploaded source should control where the documents appear to conflict?"]
                    if contradiction_notes
                    else []
                ),
            ]
        )

        for attr in ("ai_system_assessment", "risk_classification"):
            section = getattr(state, attr)
            if section is None:
                continue
            setattr(
                state,
                attr,
                self._review_section(
                    section,
                    missing_labels=missing_labels,
                    weak_labels=weak_labels,
                    contradiction_notes=contradiction_notes,
                ),
            )

        state.obligations = [
            self._review_section(
                section,
                missing_labels=missing_labels,
                weak_labels=weak_labels,
                contradiction_notes=contradiction_notes,
            )
            for section in state.obligations
        ]
        state.governance_observations = [
            self._review_section(
                section,
                missing_labels=missing_labels,
                weak_labels=weak_labels,
                contradiction_notes=contradiction_notes,
            )
            for section in state.governance_observations
        ]

        if state.final_report is not None and state.final_report.limitation_notice != LIMITATION_NOTICE:
            state.final_report = state.final_report.model_copy(
                update={"limitation_notice": LIMITATION_NOTICE}
            )

        add_trace(
            state,
            "CriticUncertaintyAgent",
            "review_uncertainty_and_evidence",
            (
                f"Flagged {len(missing_labels)} missing critical facts, "
                f"{len(weak_labels)} weak-evidence facts, and {len(contradiction_notes)} visible contradictions."
            ),
        )
        return state

    def _review_section(
        self,
        section: AssessmentSection,
        missing_labels: list[str],
        weak_labels: list[str],
        contradiction_notes: list[str],
    ) -> AssessmentSection:
        uncertainties = list(section.uncertainties)
        if missing_labels:
            uncertainties.append(
                "Critical facts are missing or uncertain: " + ", ".join(missing_labels) + "."
            )
        if weak_labels:
            uncertainties.append(
                "Some extracted facts lack citation support: " + ", ".join(weak_labels) + "."
            )
        uncertainties.extend(contradiction_notes)

        confidence = section.confidence
        if missing_labels or weak_labels or contradiction_notes or not section.citations:
            confidence = _downgrade(confidence)

        return section.model_copy(
            update={
                "confidence": confidence,
                "uncertainties": dedupe(uncertainties),
            }
        )

    def _find_visible_contradictions(self, state: AgentState) -> list[str]:
        text = joined_uploaded_text(state, repo=self.repo)
        lower_text = text.lower()
        notes: list[str] = []

        if "human oversight" in lower_text and (
            "no human oversight" in lower_text or "without human oversight" in lower_text
        ):
            notes.append("Uploaded documents may conflict on whether human oversight exists.")
        if "llm" in lower_text and ("no llm" in lower_text or "does not use an llm" in lower_text):
            notes.append("Uploaded documents may conflict on whether an LLM/GPAI component is used.")
        if "automated decision" in lower_text and "decision support only" in lower_text:
            notes.append("Uploaded documents may conflict on whether outputs are decisions or support only.")

        return notes

    def _questions_for_missing(self, labels: list[str]) -> list[str]:
        questions_by_label = {
            "Purpose": "What is the exact intended purpose of the AI system?",
            "Sector": "Which sector and AI Act use category best describe the deployment?",
            "Affected persons": "Who can be affected by the system output?",
            "Input data": "What input data, including personal data, does the system process?",
            "Outputs": "What outputs does the system produce and who acts on them?",
            "Automation level": "Which steps are automated and which are only decision support?",
            "Human oversight": "Who reviews, overrides, or monitors the system output?",
            "Deployment context": "Where will the system be deployed and in which EU workflow?",
        }
        return [questions_by_label[label] for label in labels if label in questions_by_label]

    def _questions_for_weak_evidence(self, labels: list[str]) -> list[str]:
        return [f"Can you upload source evidence for {label}?" for label in labels]


def _downgrade(confidence: str) -> str:
    if confidence == "high":
        return "medium"
    if confidence == "medium":
        return "low"
    return "low"
