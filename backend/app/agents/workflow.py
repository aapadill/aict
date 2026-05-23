from __future__ import annotations

from dataclasses import dataclass

from app.agents.ai_system_definition_agent import AISystemDefinitionAgent
from app.agents.critic_uncertainty_agent import CriticUncertaintyAgent
from app.agents.document_fact_agent import DocumentFactAgent
from app.agents.obligations_governance_agent import ObligationsGovernanceAgent
from app.agents.risk_classification_agent import RiskClassificationAgent
from app.models.analysis import (
    AgentState,
    AnalysisResult,
    LIMITATION_NOTICE,
    empty_section,
)
from app.services.citation_verifier import verify_analysis_citations
from app.services.retrieval import index_case
from app.storage import JsonRepository, repository


@dataclass(frozen=True)
class AnalysisWorkflowError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def run_analysis_workflow(
    case_id: str,
    repo: JsonRepository = repository,
) -> AnalysisResult:
    case = repo.get_case(case_id)
    if case is None:
        raise AnalysisWorkflowError("case_not_found", f"Case '{case_id}' was not found.")

    documents = repo.list_documents(case_id)
    if not documents:
        raise AnalysisWorkflowError(
            "no_documents",
            "Upload at least one supporting document before running analysis.",
        )

    index_case(case_id, repo=repo)

    state = AgentState(case_id=case_id)
    for agent in (
        DocumentFactAgent(repo=repo),
        AISystemDefinitionAgent(repo=repo),
        RiskClassificationAgent(repo=repo),
        ObligationsGovernanceAgent(repo=repo),
        CriticUncertaintyAgent(repo=repo),
    ):
        agent.run(state)

    draft = assemble_analysis_result(state)
    verified = verify_analysis_citations(draft, repo=repo)
    verified = _normalize_top_level_citations(verified)
    state.final_report = verified
    repo.save_analysis(case_id=case_id, result=verified.model_dump(mode="json"), status="complete")
    return verified


def assemble_analysis_result(state: AgentState) -> AnalysisResult:
    ai_system_assessment = state.ai_system_assessment or empty_section(
        "AI-system definition assessment"
    )
    risk_classification = state.risk_classification or empty_section("Risk classification")
    citations = _unique_citations(
        [
            *state.citations,
            *[citation for fact in state.facts for citation in fact.citations],
            *ai_system_assessment.citations,
            *risk_classification.citations,
            *[citation for section in state.obligations for citation in section.citations],
            *[
                citation
                for section in state.governance_observations
                for citation in section.citations
            ],
        ]
    )

    return AnalysisResult(
        case_id=state.case_id,
        summary=state.summary
        or "The uploaded documents do not yet provide enough information for a useful use-case summary.",
        extracted_facts=state.facts,
        ai_system_assessment=ai_system_assessment,
        risk_classification=risk_classification,
        obligations=state.obligations,
        governance_observations=state.governance_observations,
        missing_information=_dedupe([*state.missing_information, *state.uncertainties]),
        follow_up_questions=_dedupe(state.follow_up_questions),
        citations=citations,
        agent_trace=state.agent_trace,
        limitation_notice=LIMITATION_NOTICE,
    )


def latest_analysis_result(
    case_id: str,
    repo: JsonRepository = repository,
) -> AnalysisResult | None:
    analysis = repo.get_latest_analysis(case_id)
    if analysis is None:
        return None
    return AnalysisResult.model_validate(analysis.result)


def _normalize_top_level_citations(result: AnalysisResult) -> AnalysisResult:
    nested = _unique_citations(
        [
            *[citation for fact in result.extracted_facts for citation in fact.citations],
            *result.ai_system_assessment.citations,
            *result.risk_classification.citations,
            *[citation for section in result.obligations for citation in section.citations],
            *[
                citation
                for section in result.governance_observations
                for citation in section.citations
            ],
            *result.citations,
        ]
    )
    return result.model_copy(update={"citations": nested, "limitation_notice": LIMITATION_NOTICE})


def _unique_citations(citations: list) -> list:
    seen: set[str] = set()
    unique: list = []
    for citation in citations:
        key = citation.chunk_id or citation.id
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped
