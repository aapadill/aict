from __future__ import annotations

import re
from collections.abc import Iterable

from app.models.analysis import AgentState, AgentTraceEvent, Citation
from app.services.citation_utils import normalize_for_citation
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


def first_sentence(text: str, max_length: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    sentence_match = re.search(r"(.+?[.!?])(?:\s|$)", compact)
    sentence = sentence_match.group(1) if sentence_match else compact
    if len(sentence) <= max_length:
        return sentence
    return sentence[: max_length - 1].rstrip() + "..."


def best_snippet(citations: list[Citation]) -> str:
    return first_sentence(citations[0].snippet) if citations else ""


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
