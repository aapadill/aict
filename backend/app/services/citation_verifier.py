from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models.analysis import AnalysisResult, AssessmentSection, Citation, ExtractedFact
from app.services.citation_utils import normalize_for_citation, quote_hash, tokenize
from app.storage import Chunk, JsonRepository, repository


@dataclass(frozen=True)
class VerifiedCitationResult:
    citation: Citation
    verified: bool
    reason: str | None = None
    match_type: str | None = None


def verify_citation(
    citation: Citation,
    repo: JsonRepository = repository,
) -> VerifiedCitationResult:
    chunk = _resolve_chunk(citation, repo)
    if chunk is None:
        return VerifiedCitationResult(citation=citation, verified=False, reason="chunk_not_found")

    metadata_error = _metadata_error(citation, chunk, repo)
    if metadata_error:
        return VerifiedCitationResult(citation=citation, verified=False, reason=metadata_error)

    snippet = normalize_for_citation(citation.snippet)
    chunk_text = normalize_for_citation(chunk.text)
    if not snippet:
        return VerifiedCitationResult(citation=citation, verified=False, reason="empty_snippet")

    expected_hash = quote_hash(citation.snippet)
    if citation.quote_hash and citation.quote_hash != expected_hash:
        return VerifiedCitationResult(citation=citation, verified=False, reason="quote_hash_mismatch")

    if snippet in chunk_text:
        return VerifiedCitationResult(
            citation=_verified_citation(citation, expected_hash),
            verified=True,
            match_type="exact_normalized_substring",
        )

    if _strict_near_match(snippet, chunk_text):
        return VerifiedCitationResult(
            citation=_verified_citation(citation, expected_hash),
            verified=True,
            match_type="strict_token_overlap",
        )

    return VerifiedCitationResult(citation=citation, verified=False, reason="snippet_not_in_chunk")


def verify_citations(
    citations: list[Citation],
    repo: JsonRepository = repository,
) -> list[Citation]:
    return [
        result.citation
        for result in (verify_citation(citation, repo=repo) for citation in citations)
        if result.verified
    ]


def verify_analysis_citations(
    result: AnalysisResult,
    repo: JsonRepository = repository,
) -> AnalysisResult:
    invalid_count = 0

    facts: list[ExtractedFact] = []
    for fact in result.extracted_facts:
        verified, removed = _verified_list(fact.citations, repo)
        invalid_count += removed
        facts.append(
            fact.model_copy(
                update={
                    "citations": verified,
                    "status": "uncertain" if removed and fact.status == "found" else fact.status,
                }
            )
        )

    ai_system_assessment, removed = _verify_section(result.ai_system_assessment, repo)
    invalid_count += removed
    risk_classification, removed = _verify_section(result.risk_classification, repo)
    invalid_count += removed

    obligations: list[AssessmentSection] = []
    for section in result.obligations:
        verified_section, removed = _verify_section(section, repo)
        invalid_count += removed
        obligations.append(verified_section)

    governance_observations: list[AssessmentSection] = []
    for section in result.governance_observations:
        verified_section, removed = _verify_section(section, repo)
        invalid_count += removed
        governance_observations.append(verified_section)

    citations, removed = _verified_list(result.citations, repo)
    invalid_count += removed
    missing_information = list(result.missing_information)
    if invalid_count:
        missing_information.append(
            "A generated citation could not be verified against the stored source text."
        )

    return result.model_copy(
        update={
            "extracted_facts": facts,
            "ai_system_assessment": ai_system_assessment,
            "risk_classification": risk_classification,
            "obligations": obligations,
            "governance_observations": governance_observations,
            "citations": citations,
            "missing_information": _dedupe(missing_information),
        }
    )


def _resolve_chunk(citation: Citation, repo: JsonRepository) -> Chunk | None:
    if citation.chunk_id:
        return repo.get_chunk(citation.chunk_id)
    return repo.get_chunk(citation.id)


def _metadata_error(citation: Citation, chunk: Chunk, repo: JsonRepository) -> str | None:
    if citation.source_type != chunk.sourcetype:
        return "source_type_mismatch"
    if citation.source_title != chunk.sourcetitle:
        return "source_title_mismatch"
    if citation.location != chunk.location:
        return "location_mismatch"
    if citation.source_id is not None and citation.source_id != chunk.sourceid:
        return "source_id_mismatch"
    if citation.document_id is not None and citation.document_id != chunk.documentid:
        return "document_id_mismatch"

    if chunk.sourcetype == "uploaded_document":
        document_id = citation.document_id or chunk.documentid
        if not document_id or repo.get_document(document_id) is None:
            return "uploaded_document_not_found"
    elif chunk.documentid:
        return "regulatory_chunk_has_document_id"

    return None


def _verified_citation(citation: Citation, expected_hash: str) -> Citation:
    return citation.model_copy(update={"quote_hash": expected_hash, "verified": True})


def _strict_near_match(snippet: str, chunk_text: str) -> bool:
    snippet_tokens = tokenize(snippet)
    if len(snippet_tokens) < 4:
        return False
    chunk_tokens = set(tokenize(chunk_text))
    if not chunk_tokens:
        return False
    overlap = sum(1 for token in snippet_tokens if token in chunk_tokens) / len(snippet_tokens)
    return overlap >= 0.92


def _verified_list(
    citations: Iterable[Citation],
    repo: JsonRepository,
) -> tuple[list[Citation], int]:
    results = [verify_citation(citation, repo=repo) for citation in citations]
    verified = [result.citation for result in results if result.verified]
    return verified, sum(1 for result in results if not result.verified)


def _verify_section(
    section: AssessmentSection,
    repo: JsonRepository,
) -> tuple[AssessmentSection, int]:
    verified, removed = _verified_list(section.citations, repo)
    uncertainties = list(section.uncertainties)
    confidence = section.confidence
    if removed:
        uncertainties.append(
            "A generated citation could not be verified against the stored source text."
        )
        if confidence == "high":
            confidence = "medium"
        elif confidence == "medium":
            confidence = "low"

    return (
        section.model_copy(
            update={
                "citations": verified,
                "uncertainties": _dedupe(uncertainties),
                "confidence": confidence,
            }
        ),
        removed,
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped
