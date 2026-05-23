from pathlib import Path

import pytest

from app.agents import workflow as workflow_module
from app.agents.risk_classification_agent import RiskClassificationAgent as RealRiskClassificationAgent
from app.agents.workflow import run_analysis_workflow
from app.models.analysis import Citation
from app.storage.json_repository import JsonRepository


def test_run_analysis_workflow_saves_schema_valid_result(tmp_path: Path) -> None:
    repo, case_id = _sample_repo(tmp_path)

    result = run_analysis_workflow(case_id, repo=repo)
    saved = repo.get_latest_analysis(case_id)

    assert result.case_id == case_id
    assert result.summary
    assert saved is not None
    assert saved.status == "complete"
    assert saved.result["case_id"] == case_id
    assert result.agent_trace
    assert [event.agent for event in result.agent_trace] == [
        "DocumentFactAgent",
        "AISystemDefinitionAgent",
        "RiskClassificationAgent",
        "ObligationsGovernanceAgent",
        "CriticUncertaintyAgent",
    ]
    assert result.follow_up_questions
    assert result.limitation_notice == "This is a decision-support draft, not final legal advice."
    assert result.citations
    assert all(citation.verified is True for citation in result.citations)


def test_workflow_verification_removes_injected_fake_citation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, case_id = _sample_repo(tmp_path)

    class HallucinatingRiskAgent:
        def __init__(self, repo: JsonRepository) -> None:
            self.repo = repo

        def run(self, state):
            RealRiskClassificationAgent(repo=self.repo).run(state)
            fake = Citation(
                id="citation_fake",
                chunk_id="chunk_fake",
                source_type="legislation",
                source_title="Invented source",
                location="Article 999",
                snippet="This source text does not exist.",
            )
            state.risk_classification.citations.append(fake)
            state.citations.append(fake)
            return state

    monkeypatch.setattr(workflow_module, "RiskClassificationAgent", HallucinatingRiskAgent)

    result = run_analysis_workflow(case_id, repo=repo)
    saved = repo.get_latest_analysis(case_id)

    assert all(citation.chunk_id != "chunk_fake" for citation in result.citations)
    assert all(
        citation.chunk_id != "chunk_fake"
        for citation in result.risk_classification.citations
    )
    assert (
        "A generated citation could not be verified against the stored source text."
        in result.risk_classification.uncertainties
    )
    assert (
        "A generated citation could not be verified against the stored source text."
        in saved.result["missing_information"]
    )


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
