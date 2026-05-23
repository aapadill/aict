from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.agents.workflow import latest_analysis_result
from app.core.config import settings
from app.models.analysis import AnalysisResult, Citation
from app.services import llm as llm_service
from app.services.citation_verifier import verify_citations
from app.services.retrieval import search_case
from app.storage import JsonRepository, repository

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an EU AI Act compliance assistant. You answer follow-up questions based on a saved
first-pass assessment and retrieved source evidence.

Rules:
- Ground every claim in the saved assessment or a provided source chunk.
- Be direct but cautious. Uncertainty is a feature, not a bug.
- Never give a definitive legal conclusion ("this is compliant" or "this is illegal").
- If a source chunk supports your point, reference it as [chunk_id].
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

    repo.save_message(case_id=case_id, role="user", content=text, citations=[])

    new_facts = detect_new_facts(text)
    citations = _retrieve_and_verify(case_id, text, repo=repo)

    model = settings.chat_agent_model
    if model:
        try:
            content = _build_llm_answer(model, text, analysis, citations)
        except Exception as exc:
            logger.warning("Chat LLM call failed (%s); falling back to template answer.", exc)
            content = _build_template_answer(
                question=text, analysis=analysis, citations=citations, new_facts=new_facts
            )
    else:
        content = _build_template_answer(
            question=text, analysis=analysis, citations=citations, new_facts=new_facts
        )

    reassessment_recommended = bool(new_facts)
    if reassessment_recommended:
        content += (
            "\n\nYou provided new factual information that was not part of the saved assessment. "
            "Upload or confirm source evidence and rerun the assessment before relying on this answer."
        )

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


# ------------------------------------------------------------------
# Template-based fallback answer (original implementation)
# ------------------------------------------------------------------


def _build_template_answer(
    question: str,
    analysis: AnalysisResult,
    citations: list[Citation],
    new_facts: list[str],
) -> str:
    lower_question = question.lower()
    parts: list[str] = []

    if _asks_about_risk(lower_question):
        parts.append(
            "Based on the saved first-pass assessment, the current risk view is: "
            f"{analysis.risk_classification.conclusion}"
        )
        parts.append(
            "This should be treated as decision support, not a final legal conclusion."
        )
    elif _asks_about_next_steps(lower_question):
        next_items = analysis.missing_information[:5] or analysis.follow_up_questions[:5]
        if next_items:
            parts.append("The next useful evidence to collect is: " + "; ".join(next_items) + ".")
        else:
            parts.append(
                "The saved assessment does not list specific missing evidence, but role allocation, "
                "intended purpose, oversight, and monitoring should still be confirmed."
            )
    elif _asks_about_compliance(lower_question):
        parts.append(
            "I would not describe the system as definitely compliant from this record. "
            "The saved assessment is a first-pass review and still depends on the unresolved facts and obligations."
        )
    else:
        parts.append(
            "Using the saved assessment and retrieved sources, the most relevant current finding is: "
            f"{analysis.summary or analysis.risk_classification.conclusion}"
        )

    if analysis.ai_system_assessment.conclusion:
        parts.append(f"AI-system scope: {analysis.ai_system_assessment.conclusion}")
    if analysis.missing_information:
        parts.append(
            "Key uncertainty remains: " + "; ".join(analysis.missing_information[:4]) + "."
        )
    if citations:
        source_titles = _dedupe([citation.source_title for citation in citations])
        parts.append("I found supporting source snippets from: " + "; ".join(source_titles) + ".")
    else:
        parts.append(
            "I did not find a verified source snippet for this exact follow-up, so treat the answer as a cautious interpretation of the saved assessment."
        )
    if new_facts:
        parts.append("New fact-like statements detected: " + "; ".join(new_facts) + ".")

    return "\n\n".join(parts)


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------


def _retrieve_and_verify(case_id: str, message: str, repo: JsonRepository) -> list[Citation]:
    citations = [
        *search_case(
            case_id,
            message,
            source_types=["uploaded_document"],
            limit=3,
            repo=repo,
        ),
        *search_case(
            case_id,
            message,
            source_types=["legislation", "official_guidance", "national_guidance"],
            limit=3,
            repo=repo,
        ),
    ]
    return _dedupe_citations(verify_citations(citations, repo=repo))


def _asks_about_risk(text: str) -> bool:
    return any(term in text for term in ("high-risk", "high risk", "risk class", "classification"))


def _asks_about_next_steps(text: str) -> bool:
    return any(term in text for term in ("collect next", "next", "missing", "what should we collect"))


def _asks_about_compliance(text: str) -> bool:
    return any(term in text for term in ("compliant", "compliance", "legal", "allowed"))


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
