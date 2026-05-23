from pydantic import ValidationError

from app.models.analysis import (
    LIMITATION_NOTICE,
    REQUIRED_ANALYSIS_SECTIONS,
    REQUIRED_FACT_LABELS,
    AgentState,
    AgentTraceEvent,
    AnalysisResult,
    AssessmentSection,
    Citation,
    ExtractedFact,
    empty_analysis_result,
    empty_required_facts,
)


def test_analysis_result_serializes_to_frontend_contract_shape() -> None:
    citation = Citation(
        id="citation_1",
        source_id="source_1",
        chunk_id="chunk_1",
        source_type="uploaded_document",
        source_title="product-brief.txt",
        document_id="doc_1",
        location="page 1",
        snippet="The assistant ranks CVs before recruiter review.",
        quote_hash="hash_1",
        verified=True,
    )
    fact = ExtractedFact(
        id="fact_1",
        label="Purpose",
        value="Rank job applicants for recruiter review.",
        status="found",
        citations=[citation],
    )
    facts = empty_required_facts()
    facts[0] = fact
    ai_section = AssessmentSection(
        title="AI-system definition assessment",
        conclusion="Likely in scope.",
        confidence="medium",
        reasoning="The use case describes automated ranking of applicants.",
        citations=[citation],
        assumptions=[],
        uncertainties=["Provider role is not yet confirmed."],
    )
    risk_section = AssessmentSection(
        title="Risk classification",
        conclusion="Likely high-risk.",
        confidence="medium",
        reasoning="The use case affects employment decisions.",
        citations=[citation],
        assumptions=[],
        uncertainties=[],
    )

    result = AnalysisResult(
        case_id="case_1",
        summary="Recruiting assistant for EU hiring.",
        extracted_facts=facts,
        ai_system_assessment=ai_section,
        risk_classification=risk_section,
        obligations=[
            AssessmentSection(
                title="Roles and obligations",
                conclusion="Collect provider and deployer evidence.",
                confidence="low",
                reasoning="Roles are not established in the uploaded documents.",
                citations=[],
                assumptions=["The customer may be the deployer."],
                uncertainties=["Provider role is unclear."],
            )
        ],
        governance_observations=[],
        missing_information=["Bias testing evidence"],
        follow_up_questions=["Who is the provider?"],
        citations=[citation],
        agent_trace=[
            AgentTraceEvent(
                agent="RiskClassificationAgent",
                action="classify",
                output_summary="Flagged likely high-risk employment use case.",
            )
        ],
    )

    payload = result.model_dump(mode="json")

    assert list(payload.keys()) == [
        "case_id",
        "summary",
        "extracted_facts",
        "ai_system_assessment",
        "risk_classification",
        "obligations",
        "governance_observations",
        "missing_information",
        "follow_up_questions",
        "citations",
        "agent_trace",
        "limitation_notice",
    ]
    assert payload["citations"][0]["chunk_id"] == "chunk_1"
    assert payload["citations"][0]["verified"] is True
    assert payload["limitation_notice"] == LIMITATION_NOTICE


def test_required_fact_labels_are_available_as_empty_fact_skeletons() -> None:
    facts = empty_required_facts()

    assert tuple(fact.label for fact in facts) == REQUIRED_FACT_LABELS
    assert {fact.status for fact in facts} == {"missing"}
    assert all(fact.citations == [] for fact in facts)


def test_empty_analysis_result_contains_required_sections_and_limitation_notice() -> None:
    result = empty_analysis_result("case_1")

    assert result.case_id == "case_1"
    assert result.limitation_notice == LIMITATION_NOTICE
    assert [section.title for section in result.obligations] == ["Roles and obligations"]
    assert result.ai_system_assessment.title == "AI-system definition assessment"
    assert result.risk_classification.title == "Risk classification"
    assert "Use-case summary" in REQUIRED_ANALYSIS_SECTIONS
    assert "Citations" in REQUIRED_ANALYSIS_SECTIONS


def test_agent_state_includes_working_state_and_nested_final_report() -> None:
    final_report = empty_analysis_result("case_1")
    state = AgentState(
        case_id="case_1",
        facts=final_report.extracted_facts,
        evidence=[],
        retrieved_citations=[],
        ai_system_assessment=final_report.ai_system_assessment,
        risk_classification=final_report.risk_classification,
        obligations=final_report.obligations,
        governance_observations=[],
        assumptions=["Assume EU deployment until confirmed."],
        uncertainties=["Provider role unknown."],
        missing_information=["Provider documentation"],
        follow_up_questions=["Who operates the system?"],
        citations=[],
        agent_trace=[],
        final_report=final_report,
    )

    payload = state.model_dump(mode="json")

    assert payload["assumptions"] == ["Assume EU deployment until confirmed."]
    assert payload["uncertainties"] == ["Provider role unknown."]
    assert payload["final_report"]["limitation_notice"] == LIMITATION_NOTICE


def test_analysis_result_requires_all_required_fact_labels() -> None:
    try:
        AnalysisResult(
            case_id="case_1",
            summary="Incomplete report.",
            extracted_facts=[
                ExtractedFact(
                    id="fact_1",
                    label="Purpose",
                    value="Rank job applicants.",
                    status="found",
                    citations=[],
                )
            ],
            ai_system_assessment=AssessmentSection(
                title="AI-system definition assessment",
                conclusion="",
                confidence="low",
                reasoning="",
            ),
            risk_classification=AssessmentSection(
                title="Risk classification",
                conclusion="",
                confidence="low",
                reasoning="",
            ),
        )
    except ValidationError as exc:
        assert "AnalysisResult missing required fact labels" in str(exc)
    else:
        raise AssertionError("AnalysisResult should require all fact labels")


def test_models_reject_unknown_fields_for_stable_contract() -> None:
    try:
        Citation(
            id="citation_1",
            source_type="uploaded_document",
            source_title="brief.txt",
            snippet="Evidence",
            unsupported="field",
        )
    except ValidationError as exc:
        assert "Extra inputs are not permitted" in str(exc)
    else:
        raise AssertionError("Citation should reject unknown fields")
