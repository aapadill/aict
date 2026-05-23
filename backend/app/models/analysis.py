from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LIMITATION_NOTICE = "This is a decision-support draft, not final legal advice."

SourceType = Literal[
    "uploaded_document",
    "legislation",
    "official_guidance",
    "national_guidance",
    "commentary",
    "system",
]

FactLabel = Literal[
    "Purpose",
    "Users",
    "Affected persons",
    "Sector",
    "Input data",
    "Outputs",
    "Automation level",
    "Human oversight",
    "Deployment context",
    "Use of AI-generated content",
    "Use of GPAI/LLM",
    "Potential impact on people",
]

FactStatus = Literal["found", "missing", "uncertain"]
Confidence = Literal["low", "medium", "high"]
MessageRole = Literal["user", "assistant", "system"]

REQUIRED_FACT_LABELS: tuple[FactLabel, ...] = (
    "Purpose",
    "Users",
    "Affected persons",
    "Sector",
    "Input data",
    "Outputs",
    "Automation level",
    "Human oversight",
    "Deployment context",
    "Use of AI-generated content",
    "Use of GPAI/LLM",
    "Potential impact on people",
)

REQUIRED_ANALYSIS_SECTIONS: tuple[str, ...] = (
    "Use-case summary",
    "AI-system definition assessment",
    "Risk classification",
    "Roles and obligations",
    "Governance observations",
    "Missing information",
    "Follow-up questions",
    "Citations",
    "Agent trace",
)


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(StrictBaseModel):
    id: str
    source_id: str | None = None
    chunk_id: str | None = None
    source_type: SourceType
    source_title: str
    document_id: str | None = None
    location: str | None = None
    snippet: str
    quote_hash: str | None = None
    verified: bool | None = None


class ExtractedFact(StrictBaseModel):
    id: str
    label: FactLabel
    value: str
    status: FactStatus
    citations: list[Citation] = Field(default_factory=list)


class AssessmentSection(StrictBaseModel):
    title: str
    conclusion: str
    confidence: Confidence
    reasoning: str
    citations: list[Citation] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class AgentTraceEvent(StrictBaseModel):
    agent: str
    action: str
    output_summary: str


class AnalysisResult(StrictBaseModel):
    case_id: str
    summary: str
    extracted_facts: list[ExtractedFact]
    ai_system_assessment: AssessmentSection
    risk_classification: AssessmentSection
    obligations: list[AssessmentSection] = Field(default_factory=list)
    governance_observations: list[AssessmentSection] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    agent_trace: list[AgentTraceEvent] = Field(default_factory=list)
    limitation_notice: str = LIMITATION_NOTICE

    @model_validator(mode="after")
    def require_all_fact_labels(self) -> "AnalysisResult":
        labels = {fact.label for fact in self.extracted_facts}
        missing = [label for label in REQUIRED_FACT_LABELS if label not in labels]
        if missing:
            raise ValueError(f"AnalysisResult missing required fact labels: {', '.join(missing)}")
        return self


class AgentState(StrictBaseModel):
    case_id: str
    summary: str = ""
    facts: list[ExtractedFact] = Field(default_factory=list)
    evidence: list[Citation] = Field(default_factory=list)
    retrieved_citations: list[Citation] = Field(default_factory=list)
    ai_system_assessment: AssessmentSection | None = None
    risk_classification: AssessmentSection | None = None
    obligations: list[AssessmentSection] = Field(default_factory=list)
    governance_observations: list[AssessmentSection] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    agent_trace: list[AgentTraceEvent] = Field(default_factory=list)
    final_report: AnalysisResult | None = None


def empty_required_facts() -> list[ExtractedFact]:
    return [
        ExtractedFact(
            id=f"fact_{index}",
            label=label,
            value="",
            status="missing",
            citations=[],
        )
        for index, label in enumerate(REQUIRED_FACT_LABELS, start=1)
    ]


def empty_section(title: str, confidence: Confidence = "low") -> AssessmentSection:
    return AssessmentSection(
        title=title,
        conclusion="",
        confidence=confidence,
        reasoning="",
        citations=[],
        assumptions=[],
        uncertainties=[],
    )


def empty_analysis_result(case_id: str) -> AnalysisResult:
    return AnalysisResult(
        case_id=case_id,
        summary="",
        extracted_facts=empty_required_facts(),
        ai_system_assessment=empty_section("AI-system definition assessment"),
        risk_classification=empty_section("Risk classification"),
        obligations=[empty_section("Roles and obligations")],
        governance_observations=[],
        missing_information=[],
        follow_up_questions=[],
        citations=[],
        agent_trace=[],
        limitation_notice=LIMITATION_NOTICE,
    )
