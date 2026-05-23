from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.models.analysis import AgentState, AssessmentSection
from app.services import llm as llm_service
from app.storage import JsonRepository, repository

from .utils import (
    add_trace,
    build_chunk_map,
    citations_for_ids,
    contains_any,
    dedupe,
    format_chunks_for_prompt,
    joined_uploaded_text,
    retrieve,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an EU AI Act compliance analyst assessing whether a described use case involves an AI system.

Under EU AI Act Article 3(1), an AI system is: "a machine-based system that is designed to operate \
with varying levels of autonomy and that may exhibit adaptiveness after deployment, and that, for \
explicit or implicit objectives, infers, from the input it receives, how to generate outputs such as \
predictions, content, recommendations, or decisions that can influence physical or virtual environments."

Key assessment questions:
1. Does the system produce predictions, content, recommendations, or decisions?
2. Does it operate with some level of autonomy (versus purely rule-based deterministic logic)?
3. Is it machine-based?
4. Does it influence physical or virtual environments?

Be precise: rule-based expert systems may not qualify; machine-learning or neural-network-based \
systems typically do.

Respond with valid JSON only. No markdown. No text outside the JSON object.\
"""

_USER_TEMPLATE = """\
Source chunks:
{CHUNKS}

Assess whether the described use case involves an AI system in scope of the EU AI Act Article 3(1).

Return ONLY this JSON:
{
  "conclusion": "one short, plain-language conclusion",
  "confidence": "low|medium|high",
  "reasoning": "1-2 short sentences grounded in the provided chunks",
  "uncertainties": ["only the most important remaining open questions, max 3"],
  "chunk_ids": ["chunk_ids that support the conclusion"]
}\
"""


@dataclass
class AISystemDefinitionAgent:
    repo: JsonRepository = repository

    def run(self, state: AgentState) -> AgentState:
        model = settings.ai_system_agent_model
        if model:
            try:
                return self._run_llm(state, model)
            except Exception as exc:
                logger.warning(
                    "AISystemDefinitionAgent LLM call failed (%s); falling back to heuristic.", exc
                )
        return self._run_heuristic(state)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _run_llm(self, state: AgentState, model: str) -> AgentState:
        uploaded = retrieve(
            state,
            "AI system model algorithm automated prediction recommendation decision",
            source_types=["uploaded_document"],
            limit=5,
            repo=self.repo,
        )
        regulatory = retrieve(
            state,
            "AI system definition Article 3 machine-based autonomy adaptiveness inference outputs",
            source_types=["legislation", "official_guidance"],
            limit=5,
            repo=self.repo,
        )
        all_citations = [*uploaded, *regulatory]
        chunk_map = build_chunk_map(all_citations)

        user_prompt = _USER_TEMPLATE.replace("{CHUNKS}", format_chunks_for_prompt(all_citations))
        raw = llm_service.complete(
            model, _SYSTEM_PROMPT, user_prompt, json_mode=True, max_tokens=1500
        )
        data = llm_service.parse_json(raw)

        confidence = data.get("confidence", "low")
        if confidence not in ("low", "medium", "high"):
            confidence = "low"

        state.ai_system_assessment = AssessmentSection(
            title="AI-system definition assessment",
            conclusion=data.get("conclusion", ""),
            confidence=confidence,
            reasoning=data.get("reasoning", ""),
            citations=citations_for_ids(data.get("chunk_ids", []), chunk_map),
            assumptions=["Assessment is based only on uploaded documents and built-in AI Act corpus."],
            uncertainties=dedupe(data.get("uncertainties", []))[:3],
        )
        add_trace(
            state,
            "AISystemDefinitionAgent",
            "assess_ai_system_definition",
            f"LLM assessed AI-system scope: {data.get('conclusion', '')[:120]}",
        )
        return state

    # ------------------------------------------------------------------
    # Heuristic fallback (original implementation)
    # ------------------------------------------------------------------

    def _run_heuristic(self, state: AgentState) -> AgentState:
        uploaded_text = joined_uploaded_text(state, repo=self.repo)
        regulatory_citations = retrieve(
            state,
            "AI system machine-based autonomy adaptiveness predictions recommendations decisions Article 3",
            source_types=["legislation", "official_guidance"],
            limit=3,
            repo=self.repo,
        )
        fact_citations = retrieve(
            state,
            "automated predictions recommendations decisions outputs AI system",
            source_types=["uploaded_document"],
            limit=2,
            repo=self.repo,
        )
        citations = [*fact_citations, *regulatory_citations]

        ai_signals = contains_any(
            uploaded_text,
            [
                "AI",
                "machine learning",
                "model",
                "algorithm",
                "automated",
                "prediction",
                "recommendation",
                "decision",
                "ranking",
                "score",
                "LLM",
                "language model",
            ],
        )

        if ai_signals:
            conclusion = "The uploaded material appears to describe an AI system for first-pass AI Act analysis."
            confidence = "medium" if citations else "low"
            reasoning = (
                "The use case contains signals of automated inference or model-based outputs, "
                "and retrieved AI Act reference material describes AI systems in terms of machine-based "
                "systems producing predictions, content, recommendations, or decisions."
            )
            uncertainties = ["Confirm the exact technical architecture and level of autonomy."]
        else:
            conclusion = "The uploaded material does not yet clearly establish that the technology is an AI system."
            confidence = "low"
            reasoning = (
                "The documents do not provide enough technical detail to confirm machine-based inference, "
                "autonomy, adaptiveness, or AI-generated outputs."
            )
            uncertainties = [
                "Need technical description of model logic, autonomy, inputs, and outputs.",
            ]

        state.ai_system_assessment = AssessmentSection(
            title="AI-system definition assessment",
            conclusion=conclusion,
            confidence=confidence,
            reasoning=reasoning,
            citations=citations,
            assumptions=["Assessment is based only on uploaded documents and built-in AI Act corpus."],
            uncertainties=dedupe(uncertainties),
        )
        add_trace(
            state,
            "AISystemDefinitionAgent",
            "assess_ai_system_definition",
            f"AI-system signals {'found' if ai_signals else 'not confirmed'} with {len(citations)} citations.",
        )
        return state
