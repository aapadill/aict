import json
import os
import re

import pytest

# Tests run with configured model strings so the production workflow exercises
# the same "LLM required" gate as runtime. The provider call itself is patched
# below to avoid network dependency in unit tests.
for _var in (
    "DOCUMENT_FACT_AGENT_MODEL",
    "AI_SYSTEM_AGENT_MODEL",
    "RISK_CLASSIFICATION_AGENT_MODEL",
    "OBLIGATIONS_AGENT_MODEL",
    "CRITIC_AGENT_MODEL",
    "CHAT_AGENT_MODEL",
):
    os.environ[_var] = "test:model"


@pytest.fixture(autouse=True)
def patch_llm_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import llm as llm_service

    monkeypatch.setattr(llm_service, "complete", _fake_complete)


def _fake_complete(
    model: str,
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    max_tokens: int = 2048,
) -> str:
    del model, max_tokens
    system_lower = system.lower()
    user_lower = user.lower()

    if "extract 12 specific facts" in system_lower:
        return json.dumps(_fact_extraction_response(user, user_lower))
    if "assessing whether a described use case involves an ai system" in system_lower:
        return json.dumps(_ai_system_response(user))
    if "risk classification expert" in system_lower:
        return json.dumps(_risk_response(user))
    if "obligations mapping expert" in system_lower:
        return json.dumps(_obligations_response(user))
    if "critical reviewer" in system_lower:
        return json.dumps(
            {
                "additional_missing_information": [
                    "Confirm provider and deployer role allocation."
                ],
                "additional_uncertainties": [
                    "Uploaded documents may not prove validation, bias testing, or monitoring details."
                ],
                "additional_follow_up_questions": [
                    "Which entity is the AI system provider?",
                    "What validation or bias testing has been completed?",
                ],
            }
        )

    if json_mode:
        return "{}"
    return (
        "Based on the saved assessment, the main risk is employment-related high-risk use. "
        "Review the cited evidence and unresolved facts before relying on the conclusion.\n\n"
        "This is decision support, not final legal advice."
    )


def _fact_extraction_response(user: str, user_lower: str) -> dict:
    from app.models.analysis import REQUIRED_FACT_LABELS

    uploaded_ids = _chunk_ids_by_type(user, "uploaded_document") or _chunk_ids(user)
    first_id = uploaded_ids[:1]

    is_recruiting = any(
        term in user_lower
        for term in ("rank candidates", "employment", "recruiter", "cv", "hiring")
    )
    if not is_recruiting:
        return {
            "summary": "The uploaded documents do not yet provide enough information for a useful use-case summary.",
            "facts": {
                label: {"value": "", "status": "missing", "chunk_ids": []}
                for label in REQUIRED_FACT_LABELS
            },
        }

    facts = {
        "Purpose": {
            "value": "Ranks candidates for employment before recruiter review.",
            "status": "found",
            "chunk_ids": first_id,
        },
        "Users": {
            "value": "Recruiters and HR staff.",
            "status": "found" if "recruiter" in user_lower else "uncertain",
            "chunk_ids": first_id,
        },
        "Affected persons": {
            "value": "Job candidates.",
            "status": "found" if "candidate" in user_lower else "uncertain",
            "chunk_ids": first_id,
        },
        "Sector": {
            "value": "Employment and recruitment.",
            "status": "found",
            "chunk_ids": first_id,
        },
        "Input data": {
            "value": "CVs, application answers, and recruiter notes.",
            "status": "found" if any(term in user_lower for term in ("cv", "application")) else "missing",
            "chunk_ids": first_id if any(term in user_lower for term in ("cv", "application")) else [],
        },
        "Outputs": {
            "value": "Scores, rankings, recommendations, and summaries.",
            "status": "found",
            "chunk_ids": first_id,
        },
        "Automation level": {
            "value": "The AI system ranks or scores candidates before human review.",
            "status": "found",
            "chunk_ids": first_id,
        },
        "Human oversight": {
            "value": "Recruiters review recommendations before decisions.",
            "status": "found" if any(term in user_lower for term in ("review", "oversight")) else "missing",
            "chunk_ids": first_id if any(term in user_lower for term in ("review", "oversight")) else [],
        },
        "Deployment context": {
            "value": "Internal EU hiring workflow.",
            "status": "found" if "eu" in user_lower or "hiring workflow" in user_lower else "missing",
            "chunk_ids": first_id if "eu" in user_lower or "hiring workflow" in user_lower else [],
        },
        "Use of AI-generated content": {
            "value": "Generates application summaries.",
            "status": "found" if any(term in user_lower for term in ("summary", "summar")) else "missing",
            "chunk_ids": first_id if any(term in user_lower for term in ("summary", "summar")) else [],
        },
        "Use of GPAI/LLM": {
            "value": "Uses an LLM language model.",
            "status": "found" if "llm" in user_lower or "language model" in user_lower else "missing",
            "chunk_ids": first_id if "llm" in user_lower or "language model" in user_lower else [],
        },
        "Potential impact on people": {
            "value": "Candidate ranking may affect employment opportunities.",
            "status": "found",
            "chunk_ids": first_id,
        },
    }
    return {
        "summary": "The documents describe an AI assistant that ranks candidates and supports recruiter review in a hiring workflow.",
        "facts": facts,
    }


def _ai_system_response(user: str) -> dict:
    uploaded_ids = _chunk_ids_by_type(user, "uploaded_document")
    legal_ids = _reference_chunk_ids(user)
    return {
        "conclusion": "The uploaded material appears to describe an AI system.",
        "confidence": "medium",
        "reasoning": "The use case describes a machine-based tool that ranks, scores, recommends, or summarizes candidate information.",
        "uncertainties": ["Confirm the exact model architecture and autonomy level."],
        "use_case_fact_chunk_ids": uploaded_ids,
        "legal_rule_chunk_ids": legal_ids,
        "unsupported_claims": [],
    }


def _risk_response(user: str) -> dict:
    uploaded_ids = _chunk_ids_by_type(user, "uploaded_document")
    legal_ids = _reference_chunk_ids(user)
    return {
        "conclusion": "Likely high-risk because the system supports employment candidate ranking.",
        "confidence": "medium",
        "reasoning": "The uploaded facts point to employment and candidate ranking, and Annex III covers employment and worker-management systems.",
        "uncertainties": ["Confirm the intended purpose and whether any exception applies."],
        "use_case_fact_chunk_ids": uploaded_ids,
        "legal_rule_chunk_ids": legal_ids,
        "unsupported_claims": [],
    }


def _obligations_response(user: str) -> dict:
    chunk_ids = _chunk_ids(user)
    return {
        "obligations": [
            {
                "title": "Roles and obligations",
                "conclusion": "Provider and deployer responsibilities need confirmation.",
                "confidence": "medium",
                "reasoning": "The documents describe use in hiring, but contracts and deployment responsibility determine the final role split.",
                "uncertainties": ["Confirm provider and deployer roles."],
                "assumptions": ["Assessment is based on uploaded documents."],
                "chunk_ids": chunk_ids,
            },
            {
                "title": "Transparency and labelling",
                "conclusion": "Transparency duties may be relevant if candidates or recruiters see AI-generated summaries.",
                "confidence": "medium",
                "reasoning": "The use case includes generated summaries and recruiter-facing recommendations.",
                "uncertainties": ["Confirm who sees generated summaries."],
                "assumptions": [],
                "chunk_ids": chunk_ids,
            },
            {
                "title": "GPAI obligations",
                "conclusion": "LLM-related obligations may be relevant if a general-purpose model is integrated.",
                "confidence": "medium",
                "reasoning": "The documents mention LLM use, so model-provider documentation may be needed.",
                "uncertainties": ["Confirm the LLM provider and integration pattern."],
                "assumptions": [],
                "chunk_ids": chunk_ids,
            },
        ],
        "governance_observations": [
            {
                "title": "Documentation and accountability",
                "conclusion": "Document purpose, data, model behavior, roles, and review decisions.",
                "confidence": "medium",
                "reasoning": "A hiring workflow needs traceable evidence for role clarity, risk classification, and controls.",
                "uncertainties": ["Confirm validation and bias testing status."],
                "assumptions": [],
                "chunk_ids": chunk_ids,
            },
            {
                "title": "Human oversight, monitoring, and logging",
                "conclusion": "Human review, logging, and monitoring should be operationalized.",
                "confidence": "medium",
                "reasoning": "Recruiter review is mentioned, but practical override and monitoring controls still need detail.",
                "uncertainties": ["Confirm override authority and monitoring process."],
                "assumptions": [],
                "chunk_ids": chunk_ids,
            },
        ],
        "follow_up_questions": [
            "Who is the provider of the AI system?",
            "Who deploys the system in the EU?",
            "What validation and bias testing has been completed?",
        ],
    }


def _chunk_ids(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\bchunk_[a-zA-Z0-9_:-]+\b", text)))


def _chunk_ids_by_type(text: str, source_type: str) -> list[str]:
    pattern = re.compile(
        rf'chunk_id=(chunk_[^\s|]+)\s+\|\s+source=".*\({re.escape(source_type)}\)"'
    )
    return list(dict.fromkeys(pattern.findall(text)))


def _reference_chunk_ids(text: str) -> list[str]:
    ids: list[str] = []
    for source_type in ("legislation", "official_guidance", "national_guidance"):
        ids.extend(_chunk_ids_by_type(text, source_type))
    return list(dict.fromkeys(ids))
