from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models.analysis import Citation
from app.services.citation_utils import normalize_for_citation, quote_hash, tokenize
from app.services.document_parser import parse_case_documents
from app.storage import Chunk, JsonRepository, repository

CORPUS_CASE_ID = "__corpus__"
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

_SUPPORTED_SOURCE_TYPES: set[str] = {
    "uploaded_document",
    "legislation",
    "official_guidance",
    "national_guidance",
    "commentary",
    "system",
}


def chunk_text(text: str, metadata: dict[str, Any]) -> list[Chunk]:
    clean_text = _clean_chunk_source(text)
    if not clean_text:
        return []

    case_id = str(metadata.get("case_id") or CORPUS_CASE_ID)
    source_id = metadata.get("source_id")
    source_type = _source_type(metadata.get("source_type") or "uploaded_document")
    source_title = str(metadata.get("source_title") or "Untitled source")
    document_id = metadata.get("document_id")
    location = metadata.get("location")
    created_at = str(metadata.get("created_at") or datetime.now(timezone.utc).isoformat())
    base_metadata = dict(metadata)
    text_chunks = _split_text(clean_text)
    chunks: list[Chunk] = []

    for index, chunk_body in enumerate(text_chunks, start=1):
        chunk_location = _chunk_location(location, index, len(clean_text))
        chunk_metadata = {
            **base_metadata,
            "chunk_index": index,
            "chunk_count_hint": len(text_chunks),
        }
        explicit_id = metadata.get("id")
        if explicit_id and len(text_chunks) == 1:
            chunk_id = str(explicit_id)
        elif explicit_id:
            chunk_id = f"{explicit_id}_{index}"
        else:
            stable_seed = f"{case_id}|{source_id}|{source_title}|{chunk_location}|{index}|{chunk_body}"
            chunk_id = f"chunk_{quote_hash(stable_seed)[:24]}"

        chunks.append(
            Chunk(
                id=chunk_id,
                caseid=case_id,
                sourceid=str(source_id) if source_id is not None else None,
                sourcetype=source_type,
                sourcetitle=source_title,
                documentid=str(document_id) if document_id is not None else None,
                location=chunk_location,
                text=chunk_body,
                normalizedtexthash=quote_hash(chunk_body),
                metadata=chunk_metadata,
                createdat=created_at,
            )
        )

    return chunks


def index_case(
    case_id: str,
    repo: JsonRepository = repository,
    corpus_dir: Path | None = None,
) -> None:
    if repo.get_case(case_id) is None:
        raise ValueError(f"Case '{case_id}' was not found.")

    _index_uploaded_documents(case_id, repo)
    index_corpus(repo=repo, corpus_dir=corpus_dir)


def index_corpus(
    repo: JsonRepository = repository,
    corpus_dir: Path | None = None,
) -> None:
    directory = corpus_dir or settings.ai_act_corpus_dir
    if not directory.exists():
        return

    for source_path in sorted(directory.glob("*.md")):
        metadata, body = _read_corpus_file(source_path)
        if _is_placeholder_corpus_source(source_path, metadata, body):
            continue
        source_id = metadata.get("source_id") or source_path.stem
        chunks = chunk_text(
            body,
            {
                "case_id": CORPUS_CASE_ID,
                "source_id": source_id,
                "source_type": metadata.get("source_type", "official_guidance"),
                "source_title": metadata.get("source_title", source_path.stem),
                "source_url": metadata.get("source_url"),
                "location": metadata.get("location"),
                "corpus_file": str(source_path),
            },
        )
        for chunk in chunks:
            repo.save_chunk(CORPUS_CASE_ID, asdict(chunk))


def search_case(
    case_id: str,
    query: str,
    source_types: list[str] | None = None,
    limit: int = 5,
    repo: JsonRepository = repository,
    corpus_dir: Path | None = None,
) -> list[Citation]:
    if not query.strip():
        return []
    if repo.get_case(case_id) is None:
        raise ValueError(f"Case '{case_id}' was not found.")

    if not repo.list_chunks(case_id) or not repo.list_chunks(CORPUS_CASE_ID):
        index_case(case_id, repo=repo, corpus_dir=corpus_dir)

    allowed_source_types = set(source_types or [])
    chunks = repo.list_chunks(case_id) + repo.list_chunks(CORPUS_CASE_ID)
    chunks = [chunk for chunk in chunks if not _is_placeholder_corpus_chunk(chunk)]
    if allowed_source_types:
        chunks = [chunk for chunk in chunks if chunk.sourcetype in allowed_source_types]

    scored = [
        (score, chunk)
        for chunk in chunks
        if (score := _score_chunk(query, chunk)) > 0
    ]
    scored.sort(key=lambda item: (-item[0], item[1].sourcetitle, item[1].location or ""))

    citations: list[Citation] = []
    seen_chunks: set[str] = set()
    for _score, chunk in scored:
        if chunk.id in seen_chunks:
            continue
        seen_chunks.add(chunk.id)
        snippet = _snippet_for_query(chunk.text, query)
        citations.append(
            Citation(
                id=f"citation_{chunk.id}_{quote_hash(query + snippet)[:12]}",
                source_id=chunk.sourceid,
                chunk_id=chunk.id,
                source_type=chunk.sourcetype,  # type: ignore[arg-type]
                source_title=chunk.sourcetitle,
                document_id=chunk.documentid,
                location=chunk.location,
                snippet=snippet,
                quote_hash=quote_hash(snippet),
                verified=None,
            )
        )
        if len(citations) >= limit:
            break

    return citations


def _index_uploaded_documents(case_id: str, repo: JsonRepository) -> None:
    documents = repo.list_documents(case_id)
    if not documents:
        return

    if any(document.status not in {"parsed", "empty", "unreadable", "failed"} for document in documents):
        parse_case_documents(case_id, repo=repo)

    for document in repo.list_documents(case_id):
        if document.status != "parsed" or not document.extractedtextpath:
            continue
        extracted_path = Path(document.extractedtextpath)
        if not extracted_path.exists():
            continue
        text = extracted_path.read_text(encoding="utf-8")
        for location, section_text in _split_extracted_document_sections(text):
            chunks = chunk_text(
                section_text,
                {
                    "case_id": case_id,
                    "source_id": document.id,
                    "source_type": "uploaded_document",
                    "source_title": document.filename,
                    "document_id": document.id,
                    "location": location,
                },
            )
            for chunk in chunks:
                repo.save_chunk(case_id, asdict(chunk))


def _read_corpus_file(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    header, separator, body = text.partition("---")
    if not separator:
        return (
            {
                "source_id": path.stem,
                "source_type": "official_guidance",
                "source_title": path.stem,
            },
            text,
        )

    metadata: dict[str, str] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip().lower().replace("-", "_")
        metadata[normalized_key] = value.strip()

    return metadata, body.strip()


def _is_placeholder_corpus_source(
    path: Path,
    metadata: dict[str, str],
    body: str,
) -> bool:
    haystack = "\n".join(
        [
            path.name,
            metadata.get("source_id", ""),
            metadata.get("source_title", ""),
            body[:500],
        ]
    ).lower()
    return "placeholder" in haystack or "todo:" in haystack


def _is_placeholder_corpus_chunk(chunk: Chunk) -> bool:
    if chunk.caseid != CORPUS_CASE_ID:
        return False
    haystack = "\n".join(
        [
            chunk.sourceid or "",
            chunk.sourcetitle,
            chunk.text[:500],
        ]
    ).lower()
    return "placeholder" in haystack or "todo:" in haystack


def _split_extracted_document_sections(text: str) -> list[tuple[str | None, str]]:
    page_matches = list(re.finditer(r"(?m)^--- Page (\d+) ---\s*$", text))
    if not page_matches:
        return [("page 1", text)]

    sections: list[tuple[str | None, str]] = []
    for index, match in enumerate(page_matches):
        start = match.end()
        end = page_matches[index + 1].start() if index + 1 < len(page_matches) else len(text)
        page_text = text[start:end].strip()
        if page_text:
            sections.append((f"page {match.group(1)}", page_text))
    return sections


def _clean_chunk_source(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_text(text: str) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > CHUNK_SIZE:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_paragraph(paragraph))
            continue
        if current and len(current) + len(paragraph) + 2 > CHUNK_SIZE:
            chunks.append(current.strip())
            overlap = _overlap_tail(current)
            current = f"{overlap}\n\n{paragraph}" if overlap else paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip() if current else paragraph

    if current:
        chunks.append(current.strip())
    return chunks


def _split_long_paragraph(paragraph: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + CHUNK_SIZE, len(paragraph))
        chunks.append(paragraph[start:end].strip())
        if end == len(paragraph):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return [chunk for chunk in chunks if chunk]


def _overlap_tail(text: str) -> str:
    tail = text[-CHUNK_OVERLAP:].strip()
    match = re.search(r"[\s.!?;:,]+", tail)
    if match and match.end() < len(tail):
        return tail[match.end():].strip()
    return tail


def _chunk_location(location: Any, index: int, _text_length: int) -> str | None:
    if location and index == 1:
        return str(location)
    if location:
        return f"{location}, chunk {index}"
    return f"chunk {index}"


def _source_type(value: Any) -> str:
    source_type = str(value or "uploaded_document")
    if source_type not in _SUPPORTED_SOURCE_TYPES:
        return "commentary"
    return source_type


def _score_chunk(query: str, chunk: Chunk) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0

    text_tokens = tokenize(chunk.text)
    if not text_tokens:
        return 0

    text_token_set = set(text_tokens)
    overlap = sum(1 for token in query_tokens if token in text_token_set)
    phrase_bonus = 2.0 if normalize_for_citation(query) in normalize_for_citation(chunk.text) else 0.0
    title_bonus = 0.5 * sum(1 for token in query_tokens if token in tokenize(chunk.sourcetitle))
    return float(overlap) + phrase_bonus + title_bonus


def _snippet_for_query(text: str, query: str, max_length: int = 320) -> str:
    normalized_text = normalize_for_citation(text)
    best_index = -1
    for token in tokenize(query):
        best_index = normalized_text.find(token)
        if best_index >= 0:
            break

    if best_index < 0:
        start = 0
        end = min(len(text), max_length)
        snippet = text[:max_length]
    else:
        raw_index = _approx_raw_index(text, best_index)
        start = max(0, raw_index - max_length // 3)
        end = min(len(text), start + max_length)
        snippet = text[start:end]

    snippet = _clean_snippet_window(snippet, at_start=start == 0, at_end=end == len(text))
    if len(snippet) > max_length:
        snippet = snippet[: max_length - 1].rstrip() + "..."
    return snippet


def _clean_snippet_window(snippet: str, at_start: bool, at_end: bool) -> str:
    compact = re.sub(r"\s+", " ", snippet).strip()
    if not at_start:
        trimmed = re.sub(r"^\S+\s+", "", compact, count=1)
        if len(trimmed) >= 40:
            compact = trimmed
    if not at_end:
        trimmed = re.sub(r"\s+\S*$", "", compact)
        if len(trimmed) >= 40:
            compact = trimmed
    return compact.strip(" ,;:")


def _approx_raw_index(text: str, normalized_index: int) -> int:
    # The normalized index is enough to choose an approximate local window.
    return min(len(text), normalized_index)
