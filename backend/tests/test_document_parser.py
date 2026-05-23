from pathlib import Path

from app.services.document_parser import extract_document_text, parse_case_documents
from app.storage.json_repository import JsonRepository


def test_extract_txt_saves_text_and_updates_document_status(tmp_path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Recruiting assistant", None)
    source_path = repo.upload_dir / case.id / "brief.txt"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("Ranks CVs before recruiter review.\n\n", encoding="utf-8")
    document = repo.save_document(
        case_id=case.id,
        filename="brief.txt",
        content_type="text/plain",
        file_path=source_path,
    )

    extracted = extract_document_text(document.id, repo=repo)

    assert extracted.status == "parsed"
    assert extracted.document_id == document.id
    assert extracted.source_title == "brief.txt"
    assert extracted.pages[0].page == 1
    assert extracted.pages[0].text == "Ranks CVs before recruiter review."
    updated = repo.get_document(document.id)
    assert updated is not None
    assert updated.status == "parsed"
    assert updated.extractedtextpath is not None
    assert Path(updated.extractedtextpath).read_text(encoding="utf-8").strip() == extracted.text


def test_extract_markdown_empty_file_is_flagged(tmp_path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Recruiting assistant", None)
    source_path = repo.upload_dir / case.id / "empty.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("   \n", encoding="utf-8")
    document = repo.save_document(
        case_id=case.id,
        filename="empty.md",
        content_type="text/markdown",
        file_path=source_path,
    )

    extracted = extract_document_text(document.id, repo=repo)

    assert extracted.status == "empty"
    assert extracted.text == ""
    assert extracted.pages == []
    assert "Document contains no extractable text." in extracted.warnings
    assert repo.get_document(document.id).status == "empty"


def test_extract_pdf_preserves_page_number(tmp_path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Recruiting assistant", None)
    source_path = repo.upload_dir / case.id / "brief.pdf"
    source_path.parent.mkdir(parents=True)
    _write_minimal_text_pdf(source_path, "Recruiting tool ranks candidates.")
    document = repo.save_document(
        case_id=case.id,
        filename="brief.pdf",
        content_type="application/pdf",
        file_path=source_path,
    )

    extracted = extract_document_text(document.id, repo=repo)

    assert extracted.status == "parsed"
    assert extracted.pages[0].page == 1
    assert "Recruiting tool ranks candidates." in extracted.pages[0].text
    updated = repo.get_document(document.id)
    assert updated is not None
    assert updated.status == "parsed"
    assert "--- Page 1 ---" in Path(updated.extractedtextpath).read_text(encoding="utf-8")


def test_parse_case_documents_parses_uploaded_documents_only(tmp_path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Recruiting assistant", None)
    first_path = repo.upload_dir / case.id / "brief.txt"
    first_path.parent.mkdir(parents=True)
    first_path.write_text("Candidate scores are reviewed by recruiters.", encoding="utf-8")
    second_path = repo.upload_dir / case.id / "notes.md"
    second_path.write_text("## Oversight\nRecruiters approve shortlists.", encoding="utf-8")
    repo.save_document(case_id=case.id, filename="brief.txt", file_path=first_path)
    repo.save_document(case_id=case.id, filename="notes.md", file_path=second_path)

    extracted = parse_case_documents(case.id, repo=repo)

    assert [document.status for document in extracted] == ["parsed", "parsed"]
    assert {document.source_title for document in extracted} == {"brief.txt", "notes.md"}
    assert {document.status for document in repo.list_documents(case.id)} == {"parsed"}


def test_missing_upload_file_is_marked_failed(tmp_path) -> None:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Recruiting assistant", None)
    document = repo.save_document(
        case_id=case.id,
        filename="missing.txt",
        file_path=repo.upload_dir / case.id / "missing.txt",
    )

    extracted = extract_document_text(document.id, repo=repo)

    assert extracted.status == "failed"
    assert extracted.warnings == ["Uploaded file was not found on disk."]
    assert repo.get_document(document.id).status == "failed"


def _write_minimal_text_pdf(path: Path, text: str) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        _pdf_stream(f"BT\n/F1 12 Tf\n72 720 Td\n({text}) Tj\nET\n"),
    ]

    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(obj)
        content.extend(b"\nendobj\n")

    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(content)


def _pdf_stream(content: str) -> bytes:
    encoded = content.encode("ascii")
    return b"<< /Length " + str(len(encoded)).encode("ascii") + b" >>\nstream\n" + encoded + b"endstream"
