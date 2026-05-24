import json

from app.storage.json_repository import JsonRepository


def test_initialize_creates_state_files_and_directories(tmp_path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")

    repo.initialize()

    assert repo.cases_path.exists()
    assert repo.documents_path.exists()
    assert repo.chunks_dir.is_dir()
    assert repo.analyses_dir.is_dir()
    assert repo.active_analyses_dir.is_dir()
    assert repo.messages_dir.is_dir()
    assert repo.evidence_dir.is_dir()
    assert repo.upload_dir.is_dir()
    assert repo.extracted_dir.is_dir()
    assert repo.index_dir.is_dir()
    assert json.loads(repo.cases_path.read_text()) == []
    assert json.loads(repo.documents_path.read_text()) == []


def test_repository_persists_records_and_nested_analysis(tmp_path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()

    case = repo.create_case("Recruiting assistant", "Ranks applicants for recruiter review")
    document = repo.save_document(
        case_id=case.id,
        filename="product-brief.txt",
        content_type="text/plain",
        file_path=repo.upload_dir / case.id / "product-brief.txt",
        status="parsed",
        extracted_text_path=repo.extracted_dir / case.id / "product-brief.txt",
    )
    chunk = repo.save_chunk(
        case.id,
        {
            "id": "chunk-1",
            "sourceid": document.id,
            "sourcetype": "uploaded_document",
            "sourcetitle": document.filename,
            "documentid": document.id,
            "location": "page 1",
            "text": "The tool ranks candidates before recruiter review.",
            "metadata": {"page": 1, "offset": 42},
        },
    )
    repo.save_analysis(
        case.id,
        {
            "summary": "Likely high-risk recruiting use case.",
            "obligations": [
                {
                    "title": "Human oversight",
                    "citations": [{"chunk_id": chunk.id, "snippet": "ranks candidates"}],
                }
            ],
        },
    )
    repo.save_message(
        case.id,
        "assistant",
        "Collect provider documentation next.",
        [{"chunk_id": chunk.id, "snippet": "recruiter review"}],
    )
    repo.save_evidence(
        case.id,
        {
            "id": "evidence-1",
            "sourcetype": "uploaded_document",
            "sourcetitle": document.filename,
            "documentid": document.id,
            "location": "page 1",
            "snippet": "ranks candidates",
            "metadata": {"kind": "fact"},
        },
    )

    reloaded = JsonRepository(data_dir=tmp_path / "data")
    reloaded.initialize()

    assert reloaded.get_case(case.id) == case
    assert reloaded.get_document(document.id) == document
    assert reloaded.list_documents(case.id)[0] == document
    assert reloaded.get_chunk("chunk-1", case.id) == chunk
    assert reloaded.get_chunk("chunk-1") == chunk
    assert chunk.normalizedtexthash
    assert chunk.metadata == {"page": 1, "offset": 42}
    assert reloaded.get_latest_analysis(case.id).result["obligations"][0]["citations"][0][
        "snippet"
    ] == "ranks candidates"
    assert reloaded.list_messages(case.id)[0].citations[0]["chunk_id"] == "chunk-1"
    assert reloaded.list_evidence(case.id)[0].metadata == {"kind": "fact"}


def test_repository_updates_document_status(tmp_path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Recruiting assistant", None)
    document = repo.save_document(
        case_id=case.id,
        filename="brief.txt",
        content_type="text/plain",
        status="uploaded",
    )

    updated = repo.update_document_status(
        document_id=document.id,
        status="parsed",
        extracted_text_path=repo.extracted_dir / case.id / f"{document.id}.txt",
    )

    assert updated is not None
    assert updated.status == "parsed"
    assert updated.extractedtextpath == str(repo.extracted_dir / case.id / f"{document.id}.txt")
    assert repo.get_document(document.id) == updated
