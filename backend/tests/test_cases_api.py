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
