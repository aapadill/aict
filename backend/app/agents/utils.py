from __future__ import annotations

import re
from collections.abc import Iterable

from app.models.analysis import AgentState, AgentTraceEvent, Citation
from app.services.citation_utils import normalize_for_citation, quote_hash
from app.services.retrieval import search_case
from app.storage import Chunk, JsonRepository, repository


def add_trace(state: AgentState, agent: str, action: str, output_summary: str) -> None:
    state.agent_trace.append(
        AgentTraceEvent(agent=agent, action=action, output_summary=output_summary)
    )


def add_unique_citations(state: AgentState, citations: Iterable[Citation]) -> list[Citation]:
    existing = {citation.id for citation in state.citations}
    added: list[Citation] = []
    for citation in citations:
        if citation.id in existing:
            continue
        state.citations.append(citation)
        state.retrieved_citations.append(citation)
        existing.add(citation.id)
        added.append(citation)
    return added


def retrieve(
    state: AgentState,
    query: str,
    source_types: list[str] | None = None,
    limit: int = 3,
    repo: JsonRepository = repository,
) -> list[Citation]:
    citations = search_case(
        state.case_id,
        query,
        source_types=source_types,
        limit=limit,
        repo=repo,
    )
    add_unique_citations(state, citations)
    return citations


def uploaded_chunks(state: AgentState, repo: JsonRepository = repository) -> list[Chunk]:
    return [
        chunk
        for chunk in repo.list_chunks(state.case_id)
        if chunk.sourcetype == "uploaded_document"
    ]


def joined_uploaded_text(state: AgentState, repo: JsonRepository = repository) -> str:
    return "\n\n".join(chunk.text for chunk in uploaded_chunks(state, repo=repo))


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    normalized = normalize_for_citation(text)
    for keyword in keywords:
        normalized_keyword = normalize_for_citation(keyword)
        if not normalized_keyword:
            continue
        if " " in normalized_keyword or "-" in normalized_keyword:
            if normalized_keyword in normalized:
                return True
        elif re.search(rf"\b{re.escape(normalized_keyword)}\b", normalized):
            return True
    return False


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


# ---------------------------------------------------------------------------
# LLM prompt helpers
# ---------------------------------------------------------------------------


def chunks_as_citations(chunks: list[Chunk]) -> list[Citation]:
    """Convert Chunk storage objects to Citation analysis objects.

    Uses the full chunk text (capped at 800 chars) as the snippet so the
    LLM receives as much context as possible during fact extraction.
    """
    return [
        Citation(
            id=f"citation_{chunk.id}",
            source_id=chunk.sourceid,
            chunk_id=chunk.id,
            source_type=chunk.sourcetype,  # type: ignore[arg-type]
            source_title=chunk.sourcetitle,
            document_id=chunk.documentid,
            location=chunk.location,
            snippet=chunk.text[:800],
        )
        for chunk in chunks
    ]


def format_chunks_for_prompt(citations: list[Citation]) -> str:
    """Format citations as numbered context blocks for LLM prompts."""
    if not citations:
        return "(no source chunks available)"
    parts: list[str] = []
    for i, c in enumerate(citations, 1):
        cid = c.chunk_id or c.id
        loc = f" | {c.location}" if c.location else ""
        parts.append(
            f'[{i}] chunk_id={cid} | source="{c.source_title} ({c.source_type})"{loc}\n"""\n{c.snippet}\n"""'
        )
    return "\n\n".join(parts)


def build_chunk_map(citations: list[Citation]) -> dict[str, Citation]:
    """Return chunk_id -> Citation mapping for resolving LLM-returned IDs."""
    return {c.chunk_id: c for c in citations if c.chunk_id}


def citations_for_ids(
    chunk_ids: list[str],
    chunk_map: dict[str, Citation],
) -> list[Citation]:
    """Resolve a list of chunk_id strings to Citation objects, skipping unknowns."""
    seen: set[str] = set()
    result: list[Citation] = []
    for cid in chunk_ids:
        if cid in chunk_map and cid not in seen:
            result.append(compact_citation(chunk_map[cid]))
            seen.add(cid)
    return result


def compact_citation(citation: Citation, max_length: int = 240) -> Citation:
    snippet = compact_snippet(citation.snippet, max_length=max_length)
    return citation.model_copy(
        update={
            "snippet": snippet,
            "quote_hash": quote_hash(snippet) if snippet else None,
            "verified": None,
        }
    )


def compact_snippet(text: str, max_length: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_length:
        return compact

    sentence_match = re.search(r"^(.{40,}?[.!?])(?:\s|$)", compact)
    if sentence_match and len(sentence_match.group(1)) <= max_length:
        return sentence_match.group(1)

    cutoff = compact.rfind(" ", 0, max_length - 3)
    if cutoff < max_length // 2:
        cutoff = max_length - 3
    return compact[:cutoff].rstrip(" ,;:") + "..."
