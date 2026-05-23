from pathlib import Path

from app.models.analysis import AssessmentSection, Citation, empty_analysis_result
from app.services.citation_verifier import (
    verify_analysis_citations,
    verify_citation,
    verify_citations,
)
from app.services.retrieval import CORPUS_CASE_ID, chunk_text, index_case, search_case
from app.storage.json_repository import JsonRepository


def test_chunk_text_preserves_metadata_and_stable_ids() -> None:
    chunks = chunk_text(
        "The AI system ranks candidates.\n\nRecruiters review the shortlist.",
        {
            "case_id": "case_1",
            "source_id": "doc_1",
            "source_type": "uploaded_document",
            "source_title": "brief.txt",
            "document_id": "doc_1",
            "location": "page 1",
        },
    )

    repeated = chunk_text(
        "The AI system ranks candidates.\n\nRecruiters review the shortlist.",
        {
            "case_id": "case_1",
            "source_id": "doc_1",
            "source_type": "uploaded_document",
            "source_title": "brief.txt",
            "document_id": "doc_1",
            "location": "page 1",
        },
    )

    assert len(chunks) == 1
    assert chunks[0].id == repeated[0].id
    assert chunks[0].sourcetype == "uploaded_document"
    assert chunks[0].sourcetitle == "brief.txt"
    assert chunks[0].documentid == "doc_1"
    assert chunks[0].location == "page 1"
    assert chunks[0].normalizedtexthash


def test_index_case_chunks_uploaded_documents_and_corpus(tmp_path: Path) -> None:
    repo, case_id, _corpus_dir = _repo_with_case_document_and_corpus(tmp_path)

    index_case(case_id, repo=repo, corpus_dir=tmp_path / "corpus")

    uploaded_chunks = repo.list_chunks(case_id)
    corpus_chunks = repo.list_chunks(CORPUS_CASE_ID)

    assert any("ranks candidates" in chunk.text for chunk in uploaded_chunks)
    assert any(chunk.sourcetype == "legislation" for chunk in corpus_chunks)
    assert any("Article 3" in chunk.text for chunk in corpus_chunks)


def test_search_case_returns_source_metadata_and_snippet(tmp_path: Path) -> None:
    repo, case_id, corpus_dir = _repo_with_case_document_and_corpus(tmp_path)
    index_case(case_id, repo=repo, corpus_dir=corpus_dir)

    citations = search_case(
        case_id,
        "employment candidates high risk",
        repo=repo,
        corpus_dir=corpus_dir,
        limit=3,
    )

    assert citations
    assert all(citation.chunk_id for citation in citations)
    assert all(citation.source_title for citation in citations)
    assert all(citation.source_type in {"uploaded_document", "legislation"} for citation in citations)
    assert all(citation.snippet for citation in citations)
    assert all(citation.quote_hash for citation in citations)


def test_verify_citation_accepts_real_citation_and_rejects_fake(tmp_path: Path) -> None:
    repo, case_id, corpus_dir = _repo_with_case_document_and_corpus(tmp_path)
    real_citation = search_case(
        case_id,
        "ranks candidates",
        repo=repo,
        corpus_dir=corpus_dir,
        limit=1,
    )[0]

    verified = verify_citation(real_citation, repo=repo)

    assert verified.verified is True
    assert verified.citation.verified is True
    assert verified.citation.quote_hash == real_citation.quote_hash

    fake = real_citation.model_copy(update={"chunk_id": "chunk_missing"})
    rejected = verify_citation(fake, repo=repo)

    assert rejected.verified is False
    assert rejected.reason == "chunk_not_found"
    assert verify_citations([real_citation, fake], repo=repo) == [verified.citation]


def test_verify_analysis_citations_strips_invalid_citations(tmp_path: Path) -> None:
    repo, case_id, corpus_dir = _repo_with_case_document_and_corpus(tmp_path)
    valid = search_case(
        case_id,
        "AI system definition",
        source_types=["legislation"],
        repo=repo,
        corpus_dir=corpus_dir,
        limit=1,
    )[0]
    invalid = Citation(
        id="citation_fake",
        chunk_id="chunk_fake",
        source_type="legislation",
        source_title="Made up source",
        location="Article 999",
        snippet="This text does not exist.",
    )
    result = empty_analysis_result(case_id)
    result = result.model_copy(
        update={
            "ai_system_assessment": AssessmentSection(
                title="AI-system definition assessment",
                conclusion="Likely in scope.",
                confidence="high",
                reasoning="Uses machine-based inference.",
                citations=[valid, invalid],
                assumptions=[],
                uncertainties=[],
            ),
            "citations": [valid, invalid],
        }
    )

    verified_result = verify_analysis_citations(result, repo=repo)

    assert verified_result.ai_system_assessment.confidence == "medium"
    assert verified_result.ai_system_assessment.citations == [
        verify_citation(valid, repo=repo).citation
    ]
    assert verified_result.citations == [verify_citation(valid, repo=repo).citation]
    assert (
        "A generated citation could not be verified against the stored source text."
        in verified_result.ai_system_assessment.uncertainties
    )
    assert (
        "A generated citation could not be verified against the stored source text."
        in verified_result.missing_information
    )


def _repo_with_case_document_and_corpus(tmp_path: Path) -> tuple[JsonRepository, str, Path]:
    repo = JsonRepository(data_dir=tmp_path / "data")
    repo.initialize()
    case = repo.create_case("Recruiting assistant", None)
    source_path = repo.upload_dir / case.id / "brief.txt"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "The AI system ranks candidates for employment before recruiter review.",
        encoding="utf-8",
    )
    repo.save_document(
        case_id=case.id,
        filename="brief.txt",
        content_type="text/plain",
        file_path=source_path,
    )

    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "ai-act.md").write_text(
        "\n".join(
            [
                "Source-ID: test_ai_act",
                "Source-Type: legislation",
                "Source-Title: Test AI Act excerpts",
                "Source-URL: http://data.europa.eu/eli/reg/2024/1689/oj",
                "---",
                "# Test AI Act excerpts",
                "",
                "Article 3 says an AI system can generate predictions, recommendations, or decisions.",
                "",
                "Annex III includes employment and workers management as a high-risk area.",
            ]
        ),
        encoding="utf-8",
    )

    return repo, case.id, corpus_dir
