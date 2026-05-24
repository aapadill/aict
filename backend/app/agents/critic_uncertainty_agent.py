from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.models.analysis import AgentState, AssessmentSection, LIMITATION_NOTICE
from app.services import llm as llm_service
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

_SYSTEM_PROMPT = """\
You are a critical reviewer for EU AI Act compliance assessments.

Review the draft assessment and identify:
1. Conclusions or claims that are not grounded in cited evidence (flag as uncertain)
2. Sections where the stated confidence level is too high given the supporting evidence
3. Important uncertainties or legal caveats that are missing
4. Logical gaps between the extracted facts and the risk classification or obligations
5. Follow-up questions that would resolve key outstanding uncertainties

Be constructive and specific. Your output will be merged with the existing assessment — do not
repeat information that is already present in the draft's missing_information or uncertainties lists.
Keep the output short: return at most 3 missing information items, 3 uncertainties, and 4 follow-up questions.

Respond with valid JSON only. No markdown. No text outside the JSON object.\
"""

_USER_TEMPLATE = """\
Draft assessment:
{DRAFT}

Structural flags already identified:
- Missing critical facts: {MISSING}
- Weak-evidence facts (found but no citations): {WEAK}
- Visible contradictions: {CONTRADICTIONS}

Review the draft and return ONLY this JSON:
{
  "additional_missing_information": ["new items not already listed above"],
  "additional_uncertainties": ["new uncertainty items not already in the draft"],
  "additional_follow_up_questions": ["new questions not already in the draft"]
}\
"""


@dataclass
class CriticUncertaintyAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        # Always run deterministic structural checks before the LLM critique.
        self._run_structural_review(state)

        model = settings.critic_agent_model
        if not model:
            raise RuntimeError("CRITIC_AGENT_MODEL is required.")
        self._run_llm_critique(state, model)
        return state

    # ------------------------------------------------------------------
    # LLM critique (runs on top of heuristic results)
    # ------------------------------------------------------------------

    def _run_llm_critique(self, state: AgentState, model: str) -> None:
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

        draft_text = _format_draft(state)
        user_prompt = (
            _USER_TEMPLATE
            .replace("{DRAFT}", draft_text)
            .replace("{MISSING}", ", ".join(missing_labels) or "none")
            .replace("{WEAK}", ", ".join(weak_labels) or "none")
            .replace("{CONTRADICTIONS}", "; ".join(contradiction_notes) or "none")
        )

        raw = llm_service.complete(
            model, _SYSTEM_PROMPT, user_prompt, json_mode=True, max_tokens=2000
        )
        data = llm_service.parse_json(raw)

        state.missing_information = dedupe(
            [
                *state.missing_information,
                *data.get("additional_missing_information", [])[:3],
            ]
        )
        state.uncertainties = dedupe(
            [
                *state.uncertainties,
                *data.get("additional_uncertainties", [])[:3],
            ]
        )
        state.follow_up_questions = dedupe(
            [
                *state.follow_up_questions,
                *data.get("additional_follow_up_questions", [])[:4],
            ]
        )

        add_trace(
            state,
            "CriticUncertaintyAgent",
            "review_additional_uncertainty",
            f"Added {len(data.get('additional_missing_information', []))} missing items, "
            f"{len(data.get('additional_uncertainties', []))} uncertainties, "
            f"{len(data.get('additional_follow_up_questions', []))} questions.",
        )

    # ------------------------------------------------------------------
    # Deterministic structural review (always runs)
    # ------------------------------------------------------------------

    def _run_structural_review(self, state: AgentState) -> None:
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


def _format_draft(state: AgentState) -> str:
    parts: list[str] = []

    parts.append("=== Extracted facts ===")
    for fact in state.facts:
        cited = len(fact.citations)
        parts.append(f"- {fact.label} [{fact.status}, {cited} citation(s)]: {fact.value or '(empty)'}")

    if state.ai_system_assessment:
        a = state.ai_system_assessment
        parts.append(f"\n=== AI-system assessment ===\nConclusion: {a.conclusion}\nConfidence: {a.confidence}\nReasoning: {a.reasoning}")

    if state.risk_classification:
        r = state.risk_classification
        parts.append(f"\n=== Risk classification ===\nConclusion: {r.conclusion}\nConfidence: {r.confidence}\nReasoning: {r.reasoning}")

    if state.obligations:
        parts.append("\n=== Obligations ===")
        for s in state.obligations:
            parts.append(f"- {s.title}: {s.conclusion} (confidence: {s.confidence})")

    if state.governance_observations:
        parts.append("\n=== Governance observations ===")
        for s in state.governance_observations:
            parts.append(f"- {s.title}: {s.conclusion} (confidence: {s.confidence})")

    if state.missing_information:
        parts.append("\n=== Already flagged missing information ===")
        parts.extend(f"- {item}" for item in state.missing_information[:10])

    return "\n".join(parts)
