from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, TypeVar

from app.core.config import settings

T = TypeVar("T")


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    description: str | None
    createdat: str
    updatedat: str


@dataclass(frozen=True)
class Document:
    id: str
    caseid: str
    filename: str
    contenttype: str
    filepath: str
    status: str
    extractedtextpath: str | None
    createdat: str


@dataclass(frozen=True)
class Chunk:
    id: str
    caseid: str
    sourceid: str | None
    sourcetype: str
    sourcetitle: str
    documentid: str | None
    location: str | None
    text: str
    normalizedtexthash: str
    metadata: dict[str, Any]
    createdat: str


@dataclass(frozen=True)
class Analysis:
    id: str
    caseid: str
    status: str
    result: dict[str, Any]
    createdat: str
    updated_at: str


@dataclass(frozen=True)
class Message:
    id: str
    caseid: str
    role: str
    content: str
    citations: list[dict[str, Any]]
    createdat: str


@dataclass(frozen=True)
class Evidence:
    id: str
    caseid: str
    sourcetype: str
    sourcetitle: str
    documentid: str | None
    location: str | None
    snippet: str
    metadata: dict[str, Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _hash_text(text: str) -> str:
    return sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def _get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return default


def _model_from_dict(model_type: type[T], data: dict[str, Any]) -> T:
    field_names = {field.name for field in fields(model_type)}
    return model_type(**{name: data[name] for name in field_names})  # type: ignore[misc]


def _jsonable_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return str(path)


def _safe_case_id(case_id: str) -> str:
    if not case_id or "/" in case_id or "\\" in case_id or case_id in {".", ".."}:
        raise ValueError(f"Invalid case_id for JSON state path: {case_id!r}")
    return case_id


class JsonRepository:
    """Small JSON repository for the local hackathon backend."""

    def __init__(
        self,
        data_dir: str | Path,
        state_dir: str | Path | None = None,
        upload_dir: str | Path | None = None,
        extracted_dir: str | Path | None = None,
        index_dir: str | Path | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.state_dir = Path(state_dir) if state_dir is not None else self.data_dir / "state"
        self.upload_dir = Path(upload_dir) if upload_dir is not None else self.data_dir / "uploads"
        self.extracted_dir = (
            Path(extracted_dir) if extracted_dir is not None else self.data_dir / "extracted"
        )
        self.index_dir = Path(index_dir) if index_dir is not None else self.data_dir / "index"
        self.chunks_dir = self.state_dir / "chunks"
        self.analyses_dir = self.state_dir / "analyses"
        self.messages_dir = self.state_dir / "messages"
        self.evidence_dir = self.state_dir / "evidence"
        self.cases_path = self.state_dir / "cases.json"
        self.documents_path = self.state_dir / "documents.json"
        self._lock = threading.RLock()

    def initialize(self) -> None:
        for path in (
            self.state_dir,
            self.chunks_dir,
            self.analyses_dir,
            self.messages_dir,
            self.evidence_dir,
            self.upload_dir,
            self.extracted_dir,
            self.index_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

        for path in (self.cases_path, self.documents_path):
            if not path.exists():
                self._write_json(path, [])

    def create_case(self, title: str, description: str | None) -> Case:
        timestamp = _now()
        case = Case(
            id=_new_id("case"),
            title=title,
            description=description,
            createdat=timestamp,
            updatedat=timestamp,
        )
        with self._lock:
            cases = self._read_models(self.cases_path, Case)
            cases.append(case)
            self._write_models(self.cases_path, cases)
        return case

    def list_cases(self) -> list[Case]:
        with self._lock:
            return self._read_models(self.cases_path, Case)

    def get_case(self, case_id: str) -> Case | None:
        return next((case for case in self.list_cases() if case.id == case_id), None)

    def save_document(
        self,
        case_id: str,
        filename: str,
        content_type: str | None = None,
        file_path: str | Path | None = None,
        status: str = "uploaded",
        extracted_text_path: str | Path | None = None,
        document_id: str | None = None,
    ) -> Document:
        safe_case_id = _safe_case_id(case_id)
        (self.upload_dir / safe_case_id).mkdir(parents=True, exist_ok=True)
        (self.extracted_dir / safe_case_id).mkdir(parents=True, exist_ok=True)

        document = Document(
            id=document_id or _new_id("doc"),
            caseid=case_id,
            filename=filename,
            contenttype=content_type or "application/octet-stream",
            filepath=_jsonable_path(file_path) or str(self.upload_dir / safe_case_id / filename),
            status=status,
            extractedtextpath=_jsonable_path(extracted_text_path),
            createdat=_now(),
        )
        with self._lock:
            documents = self._read_models(self.documents_path, Document)
            documents.append(document)
            self._write_models(self.documents_path, documents)
        return document

    def list_documents(self, case_id: str) -> list[Document]:
        with self._lock:
            return [
                document
                for document in self._read_models(self.documents_path, Document)
                if document.caseid == case_id
            ]

    def save_chunk(self, case_id: str, chunk: dict[str, Any]) -> Chunk:
        text = str(_get(chunk, "text", default=""))
        metadata = _get(chunk, "metadata", "metadata_json", default={})
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}

        saved_chunk = Chunk(
            id=str(_get(chunk, "id", default=_new_id("chunk"))),
            caseid=case_id,
            sourceid=_get(chunk, "sourceid", "source_id"),
            sourcetype=str(_get(chunk, "sourcetype", "source_type", default="uploaded_document")),
            sourcetitle=str(_get(chunk, "sourcetitle", "source_title", default="Untitled source")),
            documentid=_get(chunk, "documentid", "document_id"),
            location=_get(chunk, "location"),
            text=text,
            normalizedtexthash=str(
                _get(chunk, "normalizedtexthash", "normalized_text_hash", default=_hash_text(text))
            ),
            metadata=metadata,
            createdat=str(_get(chunk, "createdat", "created_at", default=_now())),
        )
        with self._lock:
            chunks = self._read_models(self._case_list_path(self.chunks_dir, case_id), Chunk)
            chunks = [existing for existing in chunks if existing.id != saved_chunk.id]
            chunks.append(saved_chunk)
            self._write_models(self._case_list_path(self.chunks_dir, case_id), chunks)
        return saved_chunk

    def get_chunk(self, chunk_id: str, case_id: str | None = None) -> Chunk | None:
        if case_id is not None:
            return next((chunk for chunk in self.list_chunks(case_id) if chunk.id == chunk_id), None)

        with self._lock:
            for path in sorted(self.chunks_dir.glob("*.json")):
                chunks = self._read_models(path, Chunk)
                match = next((chunk for chunk in chunks if chunk.id == chunk_id), None)
                if match is not None:
                    return match
        return None

    def list_chunks(self, case_id: str) -> list[Chunk]:
        with self._lock:
            return self._read_models(self._case_list_path(self.chunks_dir, case_id), Chunk)

    def save_analysis(
        self, case_id: str, result: dict[str, Any], status: str = "complete"
    ) -> Analysis:
        timestamp = _now()
        analysis = Analysis(
            id=_new_id("analysis"),
            caseid=case_id,
            status=status,
            result=result,
            createdat=timestamp,
            updated_at=timestamp,
        )
        with self._lock:
            analyses = self._read_models(self._case_list_path(self.analyses_dir, case_id), Analysis)
            analyses.append(analysis)
            self._write_models(self._case_list_path(self.analyses_dir, case_id), analyses)
        return analysis

    def get_latest_analysis(self, case_id: str) -> Analysis | None:
        analyses = self._read_models(self._case_list_path(self.analyses_dir, case_id), Analysis)
        if not analyses:
            return None
        return max(analyses, key=lambda analysis: analysis.createdat)

    def save_message(
        self, case_id: str, role: str, content: str, citations: list[dict[str, Any]]
    ) -> Message:
        message = Message(
            id=_new_id("msg"),
            caseid=case_id,
            role=role,
            content=content,
            citations=citations,
            createdat=_now(),
        )
        with self._lock:
            messages = self._read_models(self._case_list_path(self.messages_dir, case_id), Message)
            messages.append(message)
            self._write_models(self._case_list_path(self.messages_dir, case_id), messages)
        return message

    def list_messages(self, case_id: str) -> list[Message]:
        with self._lock:
            return self._read_models(self._case_list_path(self.messages_dir, case_id), Message)

    def save_evidence(self, case_id: str, evidence: dict[str, Any]) -> Evidence:
        metadata = _get(evidence, "metadata", "metadata_json", default={})
        if not isinstance(metadata, dict):
            metadata = {"value": metadata}

        saved_evidence = Evidence(
            id=str(_get(evidence, "id", default=_new_id("evidence"))),
            caseid=case_id,
            sourcetype=str(
                _get(evidence, "sourcetype", "source_type", default="uploaded_document")
            ),
            sourcetitle=str(_get(evidence, "sourcetitle", "source_title", default="Untitled source")),
            documentid=_get(evidence, "documentid", "document_id"),
            location=_get(evidence, "location"),
            snippet=str(_get(evidence, "snippet", default="")),
            metadata=metadata,
        )
        with self._lock:
            evidence_items = self._read_models(
                self._case_list_path(self.evidence_dir, case_id), Evidence
            )
            evidence_items = [item for item in evidence_items if item.id != saved_evidence.id]
            evidence_items.append(saved_evidence)
            self._write_models(self._case_list_path(self.evidence_dir, case_id), evidence_items)
        return saved_evidence

    def list_evidence(self, case_id: str) -> list[Evidence]:
        with self._lock:
            return self._read_models(self._case_list_path(self.evidence_dir, case_id), Evidence)

    def _case_list_path(self, directory: Path, case_id: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{_safe_case_id(case_id)}.json"

    def _read_models(self, path: Path, model_type: type[T]) -> list[T]:
        return [_model_from_dict(model_type, item) for item in self._read_list(path)]

    def _write_models(self, path: Path, records: list[Any]) -> None:
        self._write_json(path, [asdict(record) for record in records])

    def _read_list(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON list in {path}")
        return data

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=True, indent=2, sort_keys=True)
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


repository = JsonRepository(
    data_dir=settings.data_dir,
    state_dir=settings.state_dir,
    upload_dir=settings.upload_dir,
    extracted_dir=settings.extracted_dir,
    index_dir=settings.index_dir,
)


def initialize_storage() -> None:
    repository.initialize()


def create_case(title: str, description: str | None) -> Case:
    return repository.create_case(title, description)


def list_cases() -> list[Case]:
    return repository.list_cases()


def get_case(case_id: str) -> Case | None:
    return repository.get_case(case_id)


def save_document(
    case_id: str,
    filename: str,
    content_type: str | None = None,
    file_path: str | Path | None = None,
    status: str = "uploaded",
    extracted_text_path: str | Path | None = None,
    document_id: str | None = None,
) -> Document:
    return repository.save_document(
        case_id=case_id,
        filename=filename,
        content_type=content_type,
        file_path=file_path,
        status=status,
        extracted_text_path=extracted_text_path,
        document_id=document_id,
    )


def list_documents(case_id: str) -> list[Document]:
    return repository.list_documents(case_id)


def save_chunk(case_id: str, chunk: dict[str, Any]) -> Chunk:
    return repository.save_chunk(case_id, chunk)


def get_chunk(chunk_id: str, case_id: str | None = None) -> Chunk | None:
    return repository.get_chunk(chunk_id, case_id)


def list_chunks(case_id: str) -> list[Chunk]:
    return repository.list_chunks(case_id)


def save_analysis(case_id: str, result: dict[str, Any], status: str = "complete") -> Analysis:
    return repository.save_analysis(case_id, result, status)


def get_latest_analysis(case_id: str) -> Analysis | None:
    return repository.get_latest_analysis(case_id)


def save_message(
    case_id: str, role: str, content: str, citations: list[dict[str, Any]]
) -> Message:
    return repository.save_message(case_id, role, content, citations)


def list_messages(case_id: str) -> list[Message]:
    return repository.list_messages(case_id)


def save_evidence(case_id: str, evidence: dict[str, Any]) -> Evidence:
    return repository.save_evidence(case_id, evidence)


def list_evidence(case_id: str) -> list[Evidence]:
    return repository.list_evidence(case_id)
