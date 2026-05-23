from __future__ import annotations

import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from app.storage import Document, JsonRepository, repository

DocumentParseStatus = Literal["parsed", "empty", "unreadable", "failed"]


@dataclass(frozen=True)
class ExtractedPage:
    page: int
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    document_id: str
    source_title: str
    text: str
    pages: list[ExtractedPage]
    status: DocumentParseStatus
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def extract_document_text(
    document_id: str,
    repo: JsonRepository = repository,
) -> ExtractedDocument:
    document = repo.get_document(document_id)
    if document is None:
        raise ValueError(f"Document '{document_id}' was not found.")

    extracted = _extract_document(document)
    extracted_path = None
    if extracted.status in {"parsed", "empty"}:
        extracted_path = _save_extracted_text(repo, document, extracted)

    repo.update_document_status(
        document_id=document.id,
        status=extracted.status,
        extracted_text_path=extracted_path,
    )
    return extracted


def parse_case_documents(
    case_id: str,
    repo: JsonRepository = repository,
) -> list[ExtractedDocument]:
    if repo.get_case(case_id) is None:
        raise ValueError(f"Case '{case_id}' was not found.")

    return [
        extract_document_text(document.id, repo=repo)
        for document in repo.list_documents(case_id)
    ]


def _extract_document(document: Document) -> ExtractedDocument:
    path = Path(document.filepath)
    extension = path.suffix.lower()

    if not path.exists():
        return _result(
            document=document,
            text="",
            pages=[],
            status="failed",
            warnings=["Uploaded file was not found on disk."],
        )

    try:
        if extension == ".pdf":
            return _extract_pdf(document, path)
        if extension in {".txt", ".md"}:
            return _extract_plain_text(document, path)

        return _result(
            document=document,
            text="",
            pages=[],
            status="failed",
            warnings=[f"Unsupported document extension '{extension or '(none)'}'."],
        )
    except Exception:
        return _result(
            document=document,
            text="",
            pages=[],
            status="failed",
            warnings=["Document parsing failed. Check that the file is readable and not corrupted."],
        )


def _extract_plain_text(document: Document, path: Path) -> ExtractedDocument:
    text, warnings = _read_text_file(path)
    cleaned = _clean_text(text)
    status: DocumentParseStatus = "parsed" if cleaned else "empty"
    if status == "empty":
        warnings.append("Document contains no extractable text.")

    pages = [ExtractedPage(page=1, text=cleaned)] if cleaned else []
    return _result(document=document, text=cleaned, pages=pages, status=status, warnings=warnings)


def _extract_pdf(document: Document, path: Path) -> ExtractedDocument:
    from pypdf import PdfReader

    warnings: list[str] = []
    pages: list[ExtractedPage] = []

    with path.open("rb") as file:
        reader = PdfReader(file)
        if reader.is_encrypted:
            try:
                decrypt_result = reader.decrypt("")
            except Exception:
                return _result(
                    document=document,
                    text="",
                    pages=[],
                    status="unreadable",
                    warnings=["PDF is encrypted and could not be opened."],
                )
            if decrypt_result == 0 and reader.is_encrypted:
                return _result(
                    document=document,
                    text="",
                    pages=[],
                    status="unreadable",
                    warnings=["PDF is encrypted and could not be opened."],
                )

        for index, page in enumerate(reader.pages, start=1):
            page_text = _clean_text(page.extract_text() or "")
            if not page_text:
                warnings.append(f"Page {index} has no extractable text.")
            pages.append(ExtractedPage(page=index, text=page_text))

    text = _combine_page_text(pages)
    if text:
        return _result(document=document, text=text, pages=pages, status="parsed", warnings=warnings)

    return _result(
        document=document,
        text="",
        pages=pages,
        status="unreadable",
        warnings=warnings
        or ["PDF has no extractable text. It may be scanned or image-only."],
    )


def _read_text_file(path: Path) -> tuple[str, list[str]]:
    raw = path.read_bytes()
    if not raw:
        return "", []

    warnings: list[str] = []
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding), warnings
        except UnicodeDecodeError:
            continue

    warnings.append("Text file was decoded with latin-1 fallback.")
    return raw.decode("latin-1"), warnings


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _combine_page_text(pages: list[ExtractedPage]) -> str:
    return "\n\n".join(page.text for page in pages if page.text).strip()


def _save_extracted_text(
    repo: JsonRepository,
    document: Document,
    extracted: ExtractedDocument,
) -> Path:
    output_dir = repo.extracted_dir / document.caseid
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{document.id}.txt"

    if len(extracted.pages) > 1 or Path(document.filepath).suffix.lower() == ".pdf":
        content = "\n\n".join(
            f"--- Page {page.page} ---\n{page.text}".rstrip() for page in extracted.pages
        )
    else:
        content = extracted.text

    _write_text_atomic(output_path, content)
    return output_path


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
            if content and not content.endswith("\n"):
                file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _result(
    document: Document,
    text: str,
    pages: list[ExtractedPage],
    status: DocumentParseStatus,
    warnings: list[str],
) -> ExtractedDocument:
    return ExtractedDocument(
        document_id=document.id,
        source_title=document.filename,
        text=text,
        pages=pages,
        status=status,
        warnings=warnings,
    )
