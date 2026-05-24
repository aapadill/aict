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
from app.core.config import settings
from app.services.citation_verifier import verify_analysis_citations
from app.services.retrieval import index_case
from app.storage import JsonRepository, repository


@dataclass(frozen=True)
class AnalysisWorkflowError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def llm_configured() -> bool:
    """Return True when all analysis agent models are configured."""
    return not _missing_analysis_models()


def _missing_analysis_models() -> list[str]:
    required = {
        "DOCUMENT_FACT_AGENT_MODEL": settings.document_fact_agent_model,
        "AI_SYSTEM_AGENT_MODEL": settings.ai_system_agent_model,
        "RISK_CLASSIFICATION_AGENT_MODEL": settings.risk_classification_agent_model,
        "OBLIGATIONS_AGENT_MODEL": settings.obligations_agent_model,
        "CRITIC_AGENT_MODEL": settings.critic_agent_model,
    }
    return [name for name, value in required.items() if not value]


def _assert_llm_configured() -> None:
    if llm_configured():
        return
    raise AnalysisWorkflowError(
        "llm_not_configured",
        (
            "Required LLM models are not configured. "
            f"Missing: {', '.join(_missing_analysis_models())}.\n"
            "Set per-agent model variables in your .env file.\n\n"
            "Example using a vLLM server:\n"
            "  VLLM_BASE_URL=http://your-server:8000/v1\n"
            "  VLLM_API_KEY=your-key\n"
            "  DOCUMENT_FACT_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct\n"
            "  AI_SYSTEM_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct\n"
            "  RISK_CLASSIFICATION_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct\n"
            "  OBLIGATIONS_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct\n"
            "  CRITIC_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct\n"
            "See .env.example for vLLM/Ollama, Anthropic, and OpenAI options."
        ),
    )


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

    _assert_llm_configured()

    index_case(case_id, repo=repo)

    state = AgentState(case_id=case_id)
    try:
        for agent in (
            DocumentFactAgent(repo=repo),
            AISystemDefinitionAgent(repo=repo),
            RiskClassificationAgent(repo=repo),
            ObligationsGovernanceAgent(repo=repo),
            CriticUncertaintyAgent(repo=repo),
        ):
            agent.run(state)
    except Exception as exc:
        raise AnalysisWorkflowError(
            "llm_call_failed",
            f"Configured LLM analysis failed: {exc}",
        ) from exc

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
    result = AnalysisResult.model_validate(analysis.result)
    return result.model_copy(update={"limitation_notice": LIMITATION_NOTICE})


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
