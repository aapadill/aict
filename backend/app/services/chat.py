from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents.workflow import latest_analysis_result
from app.core.config import settings
from app.models.analysis import AnalysisResult, Citation
from app.services import llm as llm_service
from app.services.citation_verifier import verify_citations
from app.services.retrieval import search_case
from app.storage import JsonRepository, repository

_CHAT_NOTICE = "This is decision support, not final legal advice."
_CORE_CHAT_FACTS = ("Purpose", "Outputs", "Deployment context")
_CASE_GROUNDING_FACTS = (
    "Purpose",
    "Sector",
    "Input data",
    "Outputs",
    "Automation level",
    "Human oversight",
    "Deployment context",
)

_SYSTEM_PROMPT = """\
You are an EU AI Act compliance assistant. You answer follow-up questions based on a saved
first-pass assessment and retrieved source evidence.

Rules:
- Ground every claim in the saved assessment or a provided source chunk.
- Legislation/reference chunks explain legal rules. Do not apply them to the case unless uploaded
  case facts or the saved assessment support that mapping.
- Be direct but cautious. Uncertainty is a feature, not a bug.
- Never give a definitive legal conclusion ("this is compliant" or "this is illegal").
- Do not print raw chunk IDs, citation IDs, or source IDs in prose. Citations are attached separately.
- Keep the answer focused and under 400 words.
- End every answer with: "This is decision support, not final legal advice."\
"""

_USER_TEMPLATE = """\
Question: {QUESTION}

Saved assessment summary:
{SUMMARY}

Risk classification: {RISK}

Key missing information and uncertainties:
{MISSING}

Retrieved source chunks:
{CHUNKS}\
"""


@dataclass(frozen=True)
class ChatWorkflowError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class ChatResult:
    role: str
    content: str
    citations: list[Citation]
    new_facts_detected: list[str]
    reassessment_recommended: bool


def answer_follow_up(
    case_id: str,
    message: str,
    repo: JsonRepository = repository,
) -> ChatResult:
    if repo.get_case(case_id) is None:
        raise ChatWorkflowError("case_not_found", f"Case '{case_id}' was not found.")

    text = message.strip()
    if not text:
        raise ChatWorkflowError("empty_message", "Message cannot be blank.")

    analysis = latest_analysis_result(case_id, repo=repo)
    if analysis is None:
        raise ChatWorkflowError(
            "analysis_not_found",
            "Run an analysis before asking follow-up questions.",
        )
    model = settings.chat_agent_model
    if not model:
        raise ChatWorkflowError(
            "llm_not_configured",
            "CHAT_AGENT_MODEL is required before asking follow-up questions.",
        )

    repo.save_message(case_id=case_id, role="user", content=text, citations=[])

    new_facts = detect_new_facts(text)
    lacks_case_grounding = _analysis_lacks_case_grounding(analysis)
    asks_general_law = _asks_general_legal_reference(text)
    citations = _retrieve_and_verify(
        case_id,
        text,
        analysis=analysis,
        include_reference_sources=_should_include_reference_sources(analysis, text),
        repo=repo,
    )

    if lacks_case_grounding:
        if asks_general_law:
            citations = [citation for citation in citations if citation.source_type != "uploaded_document"]
            content = _build_ungrounded_reference_answer(
                analysis=analysis,
                citations=citations,
                new_facts=new_facts,
            )
        else:
            citations = []
            content = _build_case_gap_answer(analysis=analysis, new_facts=new_facts)
    else:
        try:
            content = _build_llm_answer(model, text, analysis, citations)
        except Exception as exc:
            raise ChatWorkflowError(
                "llm_call_failed",
                f"Configured chat LLM failed: {exc}",
            ) from exc

    reassessment_recommended = bool(new_facts)
    if reassessment_recommended:
        content += (
            "\n\nYou provided new factual information that was not part of the saved assessment. "
            "Upload or confirm source evidence and rerun the assessment before relying on this answer."
        )
    content = _ensure_chat_notice(_sanitize_chat_content(content))

    repo.save_message(
        case_id=case_id,
        role="assistant",
        content=content,
        citations=[citation.model_dump(mode="json") for citation in citations],
    )

    return ChatResult(
        role="assistant",
        content=content,
        citations=citations,
        new_facts_detected=new_facts,
        reassessment_recommended=reassessment_recommended,
    )


def detect_new_facts(message: str) -> list[str]:
    facts: list[str] = []
    for sentence in _sentences(message):
        normalized = sentence.lower()
        if _looks_like_question(sentence):
            continue
        if any(marker in normalized for marker in _FACT_MARKERS):
            facts.append(sentence)
            continue
        fact_like_pattern = (
            r"\b(we|our|the system|the tool|it)\s+"
            r"(will|does|is|uses|processes|ranks|decides|deploys)\b"
        )
        if re.search(fact_like_pattern, normalized):
            facts.append(sentence)
    return _dedupe(facts)


# ------------------------------------------------------------------
# LLM answer
# ------------------------------------------------------------------


def _build_llm_answer(
    model: str,
    question: str,
    analysis: AnalysisResult,
    citations: list[Citation],
) -> str:
    from app.agents.utils import format_chunks_for_prompt

    missing_items = "; ".join(analysis.missing_information[:5]) or "none identified"
    chunks_text = format_chunks_for_prompt(citations)

    user_prompt = (
        _USER_TEMPLATE
        .replace("{QUESTION}", question)
        .replace("{SUMMARY}", analysis.summary or "(no summary available)")
        .replace("{RISK}", analysis.risk_classification.conclusion)
        .replace("{MISSING}", missing_items)
        .replace("{CHUNKS}", chunks_text)
    )

    return llm_service.complete(model, _SYSTEM_PROMPT, user_prompt, max_tokens=1500)


def _build_case_gap_answer(analysis: AnalysisResult, new_facts: list[str]) -> str:
    missing_core = _missing_core_facts(analysis)
    missing = missing_core or analysis.missing_information[:5]
    parts = [
        "The saved assessment could not ground an AI Act analysis from the uploaded material.",
        (
            "The current record does not establish the basic use-case facts needed to map "
            "risk, transparency, GPAI, or other obligations to this case."
        ),
    ]
    if missing:
        parts.append("Missing or uncertain core facts: " + "; ".join(missing) + ".")
    if new_facts:
        parts.append(
            "Your message adds possible new facts, but chat does not update the saved assessment. "
            "Add those facts to the case material and rerun analysis."
        )
    else:
        parts.append(
            "Add a plain use-case description with purpose, outputs, deployment context, users, "
            "input data, automation level, and human oversight, then rerun analysis."
        )
    return "\n\n".join(parts)


def _build_ungrounded_reference_answer(
    analysis: AnalysisResult,
    citations: list[Citation],
    new_facts: list[str],
) -> str:
    missing = _missing_core_facts(analysis)
    parts = [
        "I can point to general AI Act reference material, but I cannot apply it to this case yet.",
        (
            "The saved assessment lacks enough uploaded-document facts to connect the legal rule "
            "to the actual system."
        ),
    ]
    if citations:
        source_titles = _dedupe([citation.source_title for citation in citations])
        parts.append("Relevant reference source: " + "; ".join(source_titles) + ".")
    if missing:
        parts.append("Missing or uncertain core facts: " + "; ".join(missing) + ".")
    if new_facts:
        parts.append(
            "Your message may include new facts. Add them to the case material and rerun analysis "
            "before relying on a case-specific answer."
        )
    return "\n\n".join(parts)


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------


def _retrieve_and_verify(
    case_id: str,
    message: str,
    *,
    analysis: AnalysisResult,
    include_reference_sources: bool,
    repo: JsonRepository,
) -> list[Citation]:
    citations = [
        *search_case(
            case_id,
            message,
            source_types=["uploaded_document"],
            limit=3,
            repo=repo,
        ),
    ]
    if include_reference_sources:
        citations.extend(
            search_case(
                case_id,
                _reference_query(message, analysis),
                source_types=["legislation", "official_guidance", "national_guidance"],
                limit=3,
                repo=repo,
            )
        )
    return _dedupe_citations(verify_citations(citations, repo=repo))


def _should_include_reference_sources(analysis: AnalysisResult, message: str) -> bool:
    if _analysis_lacks_case_grounding(analysis):
        return _asks_general_legal_reference(message)
    return _asks_reference_backed_question(message)


def _reference_query(message: str, analysis: AnalysisResult) -> str:
    if _asks_general_legal_reference(message):
        return message
    return " ".join(
        item
        for item in (
            message,
            analysis.risk_classification.conclusion,
            analysis.ai_system_assessment.conclusion,
        )
        if item
    )


def _analysis_lacks_case_grounding(analysis: AnalysisResult) -> bool:
    fact_by_label = {fact.label: fact for fact in analysis.extracted_facts}
    grounded_facts = [
        fact
        for label, fact in fact_by_label.items()
        if label in _CASE_GROUNDING_FACTS and fact.status == "found"
    ]
    if len(grounded_facts) < 2:
        return True
    return not _analysis_has_uploaded_citation(analysis)


def _analysis_has_uploaded_citation(analysis: AnalysisResult) -> bool:
    return any(citation.source_type == "uploaded_document" for citation in _analysis_citations(analysis))


def _analysis_citations(analysis: AnalysisResult) -> list[Citation]:
    citations = list(analysis.citations)
    for fact in analysis.extracted_facts:
        citations.extend(fact.citations)
    citations.extend(analysis.ai_system_assessment.citations)
    citations.extend(analysis.risk_classification.citations)
    for section in [*analysis.obligations, *analysis.governance_observations]:
        citations.extend(section.citations)
    return citations


def _missing_core_facts(analysis: AnalysisResult) -> list[str]:
    fact_by_label = {fact.label: fact for fact in analysis.extracted_facts}
    return [
        label
        for label in _CORE_CHAT_FACTS
        if label not in fact_by_label or fact_by_label[label].status != "found"
    ]


def _asks_reference_backed_question(text: str) -> bool:
    lower = text.lower()
    return any(
        term in lower
        for term in (
            "ai act",
            "article",
            "annex",
            "law",
            "legal",
            "compliant",
            "compliance",
            "allowed",
            "prohibited",
            "high-risk",
            "high risk",
            "risk class",
            "classification",
            "obligation",
            "transparency",
            "labelling",
            "labeling",
            "gpai",
            "llm",
            "definition",
        )
    )


def _asks_general_legal_reference(text: str) -> bool:
    lower = text.lower()
    return any(
        term in lower
        for term in (
            "what does article",
            "article ",
            "annex ",
            "what does the ai act",
            "what does the law",
            "what does the regulation",
            "define ai system",
            "definition of ai system",
            "ai act definition",
        )
    )


def _sanitize_chat_content(content: str) -> str:
    sanitized = re.sub(r"\[[^\]]*\bchunk_[a-z0-9_:-]+[^\]]*\]", "", content, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bchunk_[a-z0-9_:-]+\b", "source", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\bcitation_[a-z0-9_:-]+\b", "citation", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"[ \t]{2,}", " ", sanitized)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized.strip()


def _ensure_chat_notice(content: str) -> str:
    if _CHAT_NOTICE.lower() in content.lower():
        return content
    return f"{content}\n\n{_CHAT_NOTICE}"


def _looks_like_question(sentence: str) -> bool:
    normalized = sentence.strip().lower()
    return normalized.endswith("?") or normalized.startswith(
        (
            "does ",
            "do ",
            "can ",
            "could ",
            "should ",
            "would ",
            "is ",
            "are ",
            "what ",
            "how ",
            "why ",
            "when ",
        )
    )


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    deduped: list[Citation] = []
    for citation in citations:
        key = citation.chunk_id or citation.id
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped


_FACT_MARKERS = (
    "we will",
    "we use",
    "we process",
    "we deploy",
    "we decided",
    "we added",
    "our system",
    "our tool",
    "the system will",
    "the system uses",
    "the system processes",
    "the tool will",
    "the tool uses",
    "it will",
    "it uses",
    "no human review",
    "without human review",
    "uses an llm",
    "does not use an llm",
)
