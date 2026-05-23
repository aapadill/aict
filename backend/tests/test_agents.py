from pathlib import Path

from app.agents import (
    AISystemDefinitionAgent,
    DocumentFactAgent,
    ObligationsGovernanceAgent,
    RiskClassificationAgent,
)
from app.models.analysis import AgentState, REQUIRED_FACT_LABELS
from app.services.citation_verifier import verify_citations
from app.services.retrieval import index_case
from app.storage.json_repository import JsonRepository


def test_core_agents_exchange_state_and_fill_required_outputs(tmp_path: Path) -> None:
    repo, case_id = _sample_repo(tmp_path)
    index_case(case_id, repo=repo)
    state = AgentState(case_id=case_id)

    DocumentFactAgent(repo=repo).run(state)
    AISystemDefinitionAgent(repo=repo).run(state)
    RiskClassificationAgent(repo=repo).run(state)
    ObligationsGovernanceAgent(repo=repo).run(state)

    assert state.summary
    assert tuple(fact.label for fact in state.facts) == REQUIRED_FACT_LABELS
    assert any(fact.status == "found" for fact in state.facts)
    assert state.ai_system_assessment is not None
    assert state.ai_system_assessment.citations
    assert state.risk_classification is not None
    assert "high-risk" in state.risk_classification.conclusion
    assert state.risk_classification.citations
    assert state.obligations
    assert state.governance_observations
    assert state.citations
    assert [event.agent for event in state.agent_trace] == [
        "DocumentFactAgent",
        "AISystemDefinitionAgent",
        "RiskClassificationAgent",
        "ObligationsGovernanceAgent",
    ]


def test_agents_only_reuse_retrieval_citations_that_resolve_to_chunks(tmp_path: Path) -> None:
    repo, case_id = _sample_repo(tmp_path)
    index_case(case_id, repo=repo)
    state = AgentState(case_id=case_id)

    for agent in (
        DocumentFactAgent(repo=repo),
        AISystemDefinitionAgent(repo=repo),
        RiskClassificationAgent(repo=repo),
        ObligationsGovernanceAgent(repo=repo),
    ):
        agent.run(state)

    chunk_ids = {
        chunk.id
        for chunk in [
            *repo.list_chunks(case_id),
            *repo.list_chunks("__corpus__"),
        ]
    }

    assert state.citations
    assert all(citation.chunk_id in chunk_ids for citation in state.citations)
    assert verify_citations(state.citations, repo=repo)


def test_agents_record_uncertainty_when_docs_are_sparse(tmp_path: Path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Sparse case", None)
    source_path = repo.upload_dir / case.id / "brief.txt"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("Internal productivity tool.", encoding="utf-8")
    repo.save_document(case_id=case.id, filename="brief.txt", file_path=source_path)
    index_case(case.id, repo=repo)
    state = AgentState(case_id=case.id)

    DocumentFactAgent(repo=repo).run(state)
    AISystemDefinitionAgent(repo=repo).run(state)
    RiskClassificationAgent(repo=repo).run(state)

    assert any(fact.status == "missing" for fact in state.facts)
    assert state.ai_system_assessment is not None
    assert state.ai_system_assessment.confidence == "low"
    assert state.ai_system_assessment.uncertainties
    assert state.risk_classification is not None
    assert state.risk_classification.confidence == "low"
    assert state.risk_classification.uncertainties


def _sample_repo(tmp_path: Path) -> tuple[JsonRepository, str]:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Hiring CV screening assistant", None)
    source_path = repo.upload_dir / case.id / "brief.txt"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "\n".join(
            [
                "The purpose of the AI system is to rank candidates for employment.",
                "Recruiters use the tool to review CVs and approve shortlists.",
                "The affected persons are job candidates.",
                "Input data includes CVs, application answers, and recruiter notes.",
                "Outputs include scores, rankings, recommendations, and generated summaries.",
                "The system uses an LLM language model to summarize applications.",
                "Human oversight exists because recruiters review recommendations before decisions.",
                "The system is deployed internally in an EU hiring workflow.",
            ]
        ),
        encoding="utf-8",
    )
    repo.save_document(
        case_id=case.id,
        filename="brief.txt",
        content_type="text/plain",
        file_path=source_path,
    )
    return repo, case.id
