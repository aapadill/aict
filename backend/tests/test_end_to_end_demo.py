from pathlib import Path

from fastapi.testclient import TestClient

from app.api.cases import get_repository
from app.main import create_app
from app.models.analysis import Citation
from app.services.citation_verifier import verify_citation
from app.storage.json_repository import JsonRepository


def test_end_to_end_demo_path_accepts_real_citation_and_rejects_fake(tmp_path: Path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo

    sample_path = Path(__file__).resolve().parents[2] / "samples" / "hiring_cv_screening_use_case.md"
    sample_bytes = sample_path.read_bytes()

    with TestClient(app) as client:
        case_response = client.post(
            "/cases",
            json={
                "title": "Hiring CV screening assistant",
                "description": "End-to-end demo case",
            },
        )
        assert case_response.status_code == 201
        case_id = case_response.json()["id"]

        upload_response = client.post(
            f"/cases/{case_id}/documents",
            files=[
                (
                    "files",
                    (
                        "hiring_cv_screening_use_case.md",
                        sample_bytes,
                        "text/markdown",
                    ),
                )
            ],
        )
        assert upload_response.status_code == 201
        assert upload_response.json()[0]["status"] == "uploaded"

        analysis_response = client.post(f"/cases/{case_id}/analyze")
        assert analysis_response.status_code == 200
        analysis = analysis_response.json()
        assert analysis["summary"]
        assert analysis["citations"]
        assert analysis["follow_up_questions"]
        assert analysis["missing_information"]
        assert analysis["risk_classification"]["citations"]
        assert analysis["agent_trace"]
        assert all(citation["verified"] is True for citation in analysis["citations"])

        real_citation = Citation.model_validate(analysis["citations"][0])
        verified_real = verify_citation(real_citation, repo=repo)
        assert verified_real.verified is True

        fake_citation = real_citation.model_copy(
            update={
                "id": "citation_fake",
                "chunk_id": "chunk_fake",
                "snippet": "This snippet is not in stored source text.",
            }
        )
        verified_fake = verify_citation(fake_citation, repo=repo)
        assert verified_fake.verified is False

        chat_response = client.post(
            f"/cases/{case_id}/chat",
            json={"message": "Does this look high-risk if it is used for hiring?"},
        )
        assert chat_response.status_code == 200
        chat = chat_response.json()
        assert chat["role"] == "assistant"
        assert "risk" in chat["content"].lower()
        assert chat["citations"]

        messages_response = client.get(f"/cases/{case_id}/messages")
        assert messages_response.status_code == 200
        messages = messages_response.json()
        assert [message["role"] for message in messages] == ["user", "assistant"]
