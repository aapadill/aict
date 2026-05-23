from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.cases import get_repository
from app.main import create_app
from app.storage.json_repository import JsonRepository


@pytest.fixture
def client_and_repo(tmp_path) -> Iterator[tuple[TestClient, JsonRepository]]:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repo

    with TestClient(app) as client:
        yield client, repo


def test_create_list_and_get_case(client_and_repo: tuple[TestClient, JsonRepository]) -> None:
    client, _repo = client_and_repo

    create_response = client.post(
        "/cases",
        json={
            "title": "Hiring CV screening assistant",
            "description": "Optional short description",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["id"].startswith("case_")
    assert created["title"] == "Hiring CV screening assistant"
    assert created["description"] == "Optional short description"
    assert created["created_at"]
    assert created["updated_at"]

    list_response = client.get("/cases")
    assert list_response.status_code == 200
    assert list_response.json() == [created]

    get_response = client.get(f"/cases/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json() == {**created, "documents": []}


def test_upload_multiple_documents_to_case(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, repo = client_and_repo
    case_id = client.post("/cases", json={"title": "Hiring assistant"}).json()["id"]

    upload_response = client.post(
        f"/cases/{case_id}/documents",
        files=[
            ("files", ("brief.txt", b"Ranks CVs before recruiter review.", "text/plain")),
            ("files", ("policy.md", b"# Governance\nHuman oversight exists.", "text/markdown")),
        ],
    )

    assert upload_response.status_code == 201
    documents = upload_response.json()
    assert [document["filename"] for document in documents] == ["brief.txt", "policy.md"]
    assert {document["status"] for document in documents} == {"uploaded"}

    stored_documents = repo.list_documents(case_id)
    assert len(stored_documents) == 2
    for document in stored_documents:
        assert document.caseid == case_id
        assert document.filepath.startswith(str(repo.upload_dir / case_id))
        assert (repo.upload_dir / case_id) in Path(document.filepath).parents
        assert Path(document.filepath).exists()
        assert document.extractedtextpath is None

    documents_response = client.get(f"/cases/{case_id}/documents")
    assert documents_response.status_code == 200
    assert documents_response.json() == documents

    detail_response = client.get(f"/cases/{case_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["documents"] == documents


def test_get_case_not_found_returns_frontend_friendly_404(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, _repo = client_and_repo

    response = client.get("/cases/case_missing")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "case_not_found"


def test_upload_rejects_unsupported_file_type(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, _repo = client_and_repo
    case_id = client.post("/cases", json={"title": "Hiring assistant"}).json()["id"]

    response = client.post(
        f"/cases/{case_id}/documents",
        files=[("files", ("spreadsheet.xlsx", b"not allowed", "application/octet-stream"))],
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "unsupported_file_type"
    assert detail["filename"] == "spreadsheet.xlsx"
    assert detail["allowed_extensions"] == [".md", ".pdf", ".txt"]


def test_upload_to_missing_case_returns_404(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, _repo = client_and_repo

    response = client.post(
        "/cases/case_missing/documents",
        files=[("files", ("brief.txt", b"content", "text/plain"))],
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "case_not_found"


def test_analyze_case_and_get_latest_analysis(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, _repo = client_and_repo
    case_id = client.post("/cases", json={"title": "Hiring assistant"}).json()["id"]
    client.post(
        f"/cases/{case_id}/documents",
        files=[
            (
                "files",
                (
                    "brief.txt",
                    b"The AI system ranks candidates for employment. Recruiters review recommendations.",
                    "text/plain",
                ),
            )
        ],
    )

    analyze_response = client.post(f"/cases/{case_id}/analyze")

    assert analyze_response.status_code == 200
    result = analyze_response.json()
    assert result["case_id"] == case_id
    assert result["extracted_facts"]
    assert result["risk_classification"]
    assert result["follow_up_questions"]
    assert result["agent_trace"][-1]["agent"] == "CriticUncertaintyAgent"
    assert all(citation["verified"] is True for citation in result["citations"])

    latest_response = client.get(f"/cases/{case_id}/analysis")
    assert latest_response.status_code == 200
    assert latest_response.json() == result


def test_analyze_missing_case_returns_404(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, _repo = client_and_repo

    response = client.post("/cases/case_missing/analyze")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "case_not_found"


def test_analyze_without_documents_returns_400(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, _repo = client_and_repo
    case_id = client.post("/cases", json={"title": "Empty case"}).json()["id"]

    response = client.post(f"/cases/{case_id}/analyze")

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "no_documents"


def test_get_analysis_without_saved_result_returns_404(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, _repo = client_and_repo
    case_id = client.post("/cases", json={"title": "No analysis yet"}).json()["id"]

    response = client.get(f"/cases/{case_id}/analysis")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "analysis_not_found"


def test_chat_answers_with_verified_citations_and_saves_messages(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, repo = client_and_repo
    case_id = _create_analyzed_case(client)

    response = client.post(
        f"/cases/{case_id}/chat",
        json={"message": "Does this look high-risk if it is used for hiring?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["role"] == "assistant"
    assert "decision support" in payload["content"]
    assert payload["reassessment_recommended"] is False
    assert payload["new_facts_detected"] == []
    assert payload["citations"]
    assert all(citation["verified"] is True for citation in payload["citations"])

    stored_messages = repo.list_messages(case_id)
    assert [message.role for message in stored_messages] == ["user", "assistant"]
    assert stored_messages[0].content == "Does this look high-risk if it is used for hiring?"
    assert stored_messages[0].citations == []
    assert stored_messages[1].citations == payload["citations"]

    history_response = client.get(f"/cases/{case_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    assert [message["role"] for message in history] == ["user", "assistant"]
    assert history[1]["citations"] == payload["citations"]


def test_chat_flags_new_fact_for_reassessment(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, repo = client_and_repo
    case_id = _create_analyzed_case(client)

    response = client.post(
        f"/cases/{case_id}/chat",
        json={
            "message": "We will remove recruiter review and the system will automatically reject candidates."
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reassessment_recommended"] is True
    assert payload["new_facts_detected"] == [
        "We will remove recruiter review and the system will automatically reject candidates."
    ]
    assert "rerun the assessment" in payload["content"]
    assert repo.list_messages(case_id)[0].role == "user"


def test_chat_requires_saved_analysis(client_and_repo: tuple[TestClient, JsonRepository]) -> None:
    client, _repo = client_and_repo
    case_id = client.post("/cases", json={"title": "No analysis yet"}).json()["id"]

    response = client.post(
        f"/cases/{case_id}/chat",
        json={"message": "Does this look high-risk?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "analysis_not_found"


def test_get_messages_missing_case_returns_404(
    client_and_repo: tuple[TestClient, JsonRepository],
) -> None:
    client, _repo = client_and_repo

    response = client.get("/cases/case_missing/messages")

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "case_not_found"


def _create_analyzed_case(client: TestClient) -> str:
    case_id = client.post("/cases", json={"title": "Hiring assistant"}).json()["id"]
    client.post(
        f"/cases/{case_id}/documents",
        files=[
            (
                "files",
                (
                    "brief.txt",
                    (
                        b"The AI system ranks candidates for employment. "
                        b"Recruiters review recommendations before decisions. "
                        b"Input data includes CVs and application answers."
                    ),
                    "text/plain",
                ),
            )
        ],
    )
    analyze_response = client.post(f"/cases/{case_id}/analyze")
    assert analyze_response.status_code == 200
    return case_id
