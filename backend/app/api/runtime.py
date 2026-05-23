from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.config import settings
from app.services import llm as llm_service

router = APIRouter(prefix="/runtime", tags=["runtime"])
logger = logging.getLogger(__name__)

MAX_INSPECT_BYTES = 12 * 1024 * 1024


class RuntimeSignal(BaseModel):
    kind: str
    value: str
    severity: str
    evidence: str


class RuntimeNode(BaseModel):
    id: str
    label: str
    kind: str
    severity: str


class RuntimeEdge(BaseModel):
    source: str
    target: str
    label: str


class RuntimeEvent(BaseModel):
    time: str
    actor: str
    action: str
    target: str
    severity: str


class RuntimeAIActAssessment(BaseModel):
    relevance: str
    risk_hint: str
    confidence: str
    summary: str
    triggers: list[str]
    follow_up_questions: list[str]
    basis: str


class RuntimeSignalReview(BaseModel):
    signal_index: int
    worker: str
    kind: str
    value: str
    severity: str
    review_mode: str
    verdict: str
    eu_ai_act_relevance: str
    note: str


class RuntimeInspectionResponse(BaseModel):
    filename: str
    size_bytes: int
    sha256: str
    file_type: str
    entropy: float
    risk_score: int
    verdict: str
    analysis_mode: str
    evaluation_basis: str
    confidence: str
    summary: str
    signals: list[RuntimeSignal]
    nodes: list[RuntimeNode]
    edges: list[RuntimeEdge]
    events: list[RuntimeEvent]
    analysis: list[str]
    ai_act: RuntimeAIActAssessment
    signal_reviews: list[RuntimeSignalReview]


class RuntimeAIStatusResponse(BaseModel):
    enabled: bool
    ready: bool
    provider: str | None
    model: str | None
    message: str


@dataclass(frozen=True)
class Indicator:
    kind: str
    value: str
    severity: str
    evidence: str


@router.get("/ai-status", response_model=RuntimeAIStatusResponse)
def runtime_ai_status() -> RuntimeAIStatusResponse:
    model = settings.runtime_analyst_model.strip()
    if not model:
        return RuntimeAIStatusResponse(
            enabled=False,
            ready=False,
            provider=None,
            model=None,
            message="AI analyst is off. Set RUNTIME_ANALYST_MODEL to enable it.",
        )
    if ":" not in model:
        return RuntimeAIStatusResponse(
            enabled=True,
            ready=False,
            provider=None,
            model=model,
            message="Invalid model format. Use provider:model-id.",
        )

    provider, model_id = model.split(":", 1)
    if provider not in {"openai", "anthropic", "gemini", "vllm"}:
        return RuntimeAIStatusResponse(
            enabled=True,
            ready=False,
            provider=provider,
            model=model_id,
            message=(
                f"AI analyst is configured for unsupported provider {provider}. "
                "Supported providers: openai, anthropic, gemini, vllm."
            ),
        )

    ready = _provider_credentials_ready(provider)
    return RuntimeAIStatusResponse(
        enabled=True,
        ready=ready,
        provider=provider,
        model=model_id,
        message=(
            f"AI analyst ready via {provider}:{model_id}."
            if ready
            else f"AI analyst configured for {provider}:{model_id}, but credentials are missing."
        ),
    )


@router.post("/inspect", response_model=RuntimeInspectionResponse)
async def inspect_runtime_artifact(
    file: UploadFile = File(...),
) -> RuntimeInspectionResponse:
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "empty_file", "message": "Upload a non-empty file."},
        )
    if len(content) > MAX_INSPECT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "file_too_large",
                "message": "Runtime inspection accepts files up to 12 MB.",
            },
        )

    filename = file.filename or "artifact.bin"
    text = _extract_printable_text(content)
    indicators = _collect_indicators(text, content)
    entropy = _entropy(content)
    file_type = _file_type(content, filename)
    heuristic_score = _risk_score(indicators, entropy, file_type)
    analyst = _runtime_analyst(
        filename=filename,
        file_type=file_type,
        size_bytes=len(content),
        entropy=entropy,
        heuristic_score=heuristic_score,
        indicators=indicators,
    )
    risk_score = analyst["risk_score"]
    verdict = _verdict(risk_score)
    nodes, edges = _graph(filename, indicators)
    events = _events(filename, indicators)
    ai_act = _ai_act_lens(filename=filename, text=text, indicators=indicators, file_type=file_type)
    signal_reviews = _signal_reviews(indicators=indicators, text=text, file_type=file_type)

    return RuntimeInspectionResponse(
        filename=filename,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        file_type=file_type,
        entropy=round(entropy, 2),
        risk_score=risk_score,
        verdict=verdict,
        analysis_mode=analyst["mode"],
        evaluation_basis=analyst["basis"],
        confidence=analyst["confidence"],
        summary=analyst["summary"],
        signals=[RuntimeSignal(**indicator.__dict__) for indicator in indicators[:24]],
        nodes=nodes,
        edges=edges,
        events=events,
        analysis=analyst["analysis"],
        ai_act=ai_act,
        signal_reviews=signal_reviews,
    )


def _extract_printable_text(content: bytes) -> str:
    chunks = re.findall(rb"[\x20-\x7e]{4,}", content)
    return "\n".join(chunk.decode("utf-8", errors="ignore") for chunk in chunks[:3000])


def _collect_indicators(text: str, content: bytes) -> list[Indicator]:
    indicators: list[Indicator] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str, severity: str, evidence: str) -> None:
        clean = value.strip().strip("'\"`<>[](){}")
        if not clean:
            return
        key = (kind, clean.lower())
        if key in seen:
            return
        seen.add(key)
        indicators.append(Indicator(kind, clean[:140], severity, evidence[:220]))

    for match in re.findall(r"https?://[^\s'\"<>]{4,}", text, flags=re.IGNORECASE):
        add("network", match, "medium", "Embedded URL-like string")

    for match in re.findall(
        r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|dev|ai|app|cloud|ru|cn|biz|info)\b",
        text,
        flags=re.IGNORECASE,
    ):
        add("domain", match, "medium", "Embedded domain-like string")

    for match in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text):
        octets = [int(part) for part in match.split(".")]
        if all(0 <= part <= 255 for part in octets):
            severity = "low" if _is_private_ip(octets) else "medium"
            add("ip", match, severity, "Embedded IPv4 address")

    for match in re.findall(r"(?:[A-Za-z]:\\[^\n\r\t]{4,}|/(?:etc|tmp|var|home|usr)/[^\n\r\t]{3,})", text):
        add("file", match, "medium", "Embedded local path string")

    process_terms = {
        "powershell": "high",
        "cmd.exe": "high",
        "wscript": "high",
        "curl": "medium",
        "wget": "medium",
        "ssh": "medium",
        "python": "low",
        "node": "low",
    }
    lowered = text.lower()
    for term, severity in process_terms.items():
        if term in lowered:
            add("process", term, severity, "Process or interpreter string present")

    if content.startswith(b"MZ"):
        add("format", "Windows PE executable signature", "medium", "File starts with MZ header")
    if content.startswith(b"\x7fELF"):
        add("format", "Linux ELF executable signature", "medium", "File starts with ELF header")
    if content.startswith(b"#!"):
        add("format", "Script shebang", "low", content[:80].decode("utf-8", errors="ignore"))

    return indicators


def _ai_act_lens(
    *,
    filename: str,
    text: str,
    indicators: list[Indicator],
    file_type: str,
) -> RuntimeAIActAssessment:
    haystack = f"{filename}\n{text}".lower()
    triggers: list[str] = []
    questions: list[str] = []

    ai_signals = _matched_terms(
        haystack,
        [
            "artificial intelligence",
            "machine learning",
            "neural",
            "model",
            "algorithm",
            "automated",
            "prediction",
            "recommendation",
            "ranking",
            "score",
            "llm",
            "language model",
            "generated content",
            "chatbot",
        ],
    )
    if ai_signals:
        triggers.append("AI-system signal: " + ", ".join(ai_signals[:5]))

    prohibited = _matched_terms(
        haystack,
        [
            "social scoring",
            "subliminal",
            "manipulative",
            "emotion recognition",
            "biometric categorisation",
            "sensitive characteristics",
            "facial scraping",
            "real-time remote biometric",
        ],
    )
    if prohibited:
        triggers.append("Prohibited-practice review signal: " + ", ".join(prohibited[:4]))

    high_risk = _matched_terms(
        haystack,
        [
            "employment",
            "hiring",
            "recruitment",
            "cv screening",
            "education",
            "vocational training",
            "credit scoring",
            "essential service",
            "law enforcement",
            "migration",
            "asylum",
            "border control",
            "critical infrastructure",
            "biometric identification",
        ],
    )
    if high_risk:
        triggers.append("Annex III high-risk context signal: " + ", ".join(high_risk[:5]))

    transparency = _matched_terms(
        haystack,
        [
            "chatbot",
            "synthetic content",
            "generated content",
            "deep fake",
            "deepfake",
            "ai generated",
            "emotion recognition",
        ],
    )
    if transparency:
        triggers.append("Article 50 transparency signal: " + ", ".join(transparency[:5]))

    network_terms = [item.value for item in indicators if item.kind in {"network", "domain", "ip"}]
    if network_terms:
        triggers.append("Runtime context signal: artifact contains external connectivity indicators.")

    if prohibited:
        risk_hint = "prohibited_review_needed"
        relevance = "likely"
        summary = (
            "The artifact contains terms that overlap with EU AI Act prohibited-practice themes. "
            "This is not a legal conclusion, but it should be reviewed before deployment."
        )
    elif high_risk and ai_signals:
        risk_hint = "high_risk_possible"
        relevance = "likely"
        summary = (
            "The artifact appears connected to an AI-enabled use case in a context that can map to "
            "Annex III high-risk areas. Confirm intended purpose, users, affected persons, and oversight."
        )
    elif transparency and ai_signals:
        risk_hint = "limited_risk_possible"
        relevance = "possible"
        summary = (
            "The artifact contains AI interaction or generated-content signals that may trigger "
            "Article 50 transparency duties."
        )
    elif ai_signals:
        risk_hint = "minimal_or_unclear"
        relevance = "possible"
        summary = (
            "The artifact contains AI-system signals, but static inspection alone does not establish "
            "risk class or regulatory role."
        )
    else:
        risk_hint = "not_assessable"
        relevance = "none"
        summary = (
            "No meaningful EU AI Act signal was found in the static artifact scan. "
            "A use-case description or system documentation is needed for assessment."
        )

    questions.extend(
        [
            "What is the intended purpose of the AI system?",
            "Who deploys it, who uses it, and who is affected by its outputs?",
            "Does it produce predictions, recommendations, rankings, decisions, or generated content?",
            "Is there human oversight before outputs affect people?",
        ]
    )
    if high_risk:
        questions.append("Does the deployment fall within an Annex III high-risk purpose or an exception?")
    if transparency:
        questions.append("Are users or affected persons clearly informed they are interacting with AI or AI-generated content?")
    if network_terms:
        questions.append("Do outbound connections match the declared product purpose and data-processing documentation?")

    confidence = "medium" if (ai_signals and (high_risk or transparency or prohibited)) else "low"
    return RuntimeAIActAssessment(
        relevance=relevance,
        risk_hint=risk_hint,
        confidence=confidence,
        summary=summary,
        triggers=triggers[:8],
        follow_up_questions=questions[:7],
        basis=(
            f"Static EU AI Act triage from artifact strings, filename, file type ({file_type}), "
            "and extracted runtime indicators. The artifact was not executed and no deployment facts were verified."
        ),
    )


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in text]


def _signal_reviews(
    *,
    indicators: list[Indicator],
    text: str,
    file_type: str,
) -> list[RuntimeSignalReview]:
    limit = max(0, min(settings.runtime_signal_review_limit, 10))
    selected = indicators[:limit]
    if not selected:
        return []

    model = settings.runtime_analyst_model
    if model:
        try:
            return _run_llm_signal_reviews(model=model, indicators=selected, text=text, file_type=file_type)
        except Exception as exc:
            logger.warning("Signal review workers failed (%s); using heuristic.", exc)

    return [
        _heuristic_signal_review(index=index, indicator=indicator)
        for index, indicator in enumerate(selected, start=1)
    ]


def _run_llm_signal_reviews(
    *,
    model: str,
    indicators: list[Indicator],
    text: str,
    file_type: str,
) -> list[RuntimeSignalReview]:
    raw = llm_service.complete(
        model=model,
        system=_SIGNAL_REVIEW_SYSTEM,
        user=json.dumps(
            {
                "file_type": file_type,
                "artifact_text_excerpt": text[:2000],
                "signals": [
                    {
                        "signal_index": index,
                        "kind": indicator.kind,
                        "value": indicator.value,
                        "severity": indicator.severity,
                        "evidence": indicator.evidence,
                    }
                    for index, indicator in enumerate(indicators, start=1)
                ],
            },
            indent=2,
        ),
        json_mode=False,
        max_tokens=1400,
    )
    parsed = _parse_signal_reviews(raw)
    reviews: list[RuntimeSignalReview] = []
    for index, indicator in enumerate(indicators, start=1):
        data = parsed.get(index)
        if data is None:
            reviews.append(_heuristic_signal_review(index=index, indicator=indicator))
            continue
        reviews.append(
            RuntimeSignalReview(
                signal_index=index,
                worker=f"signal-worker-{index}",
                kind=indicator.kind,
                value=indicator.value,
                severity=indicator.severity,
                review_mode="ai",
                verdict=_normalized_signal_verdict(
                    indicator,
                    _clean_enum(data.get("verdict", ""), {"benign", "watch", "hot"}, "watch"),
                ),
                eu_ai_act_relevance=_clean_enum(
                    data.get("eu_ai_act_relevance", ""),
                    {"none", "possible", "likely"},
                    "possible",
                ),
                note=str(data.get("note") or _heuristic_signal_review(index, indicator).note)[:400],
            )
        )
    return reviews


def _parse_signal_reviews(raw: str) -> dict[int, dict[str, str]]:
    reviews: dict[int, dict[str, str]] = {}
    current: int | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        signal_match = re.match(r"(?i)^SIGNAL\s+(\d+)\s*:?\s*$", line)
        if signal_match:
            current = int(signal_match.group(1))
            reviews.setdefault(current, {})
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized = key.strip().lower().replace("-", "_")
        if normalized == "eu_ai_act":
            normalized = "eu_ai_act_relevance"
        if normalized in {"verdict", "eu_ai_act_relevance", "note"}:
            reviews.setdefault(current, {})[normalized] = value.strip()
    return reviews


def _normalized_signal_verdict(indicator: Indicator, verdict: str) -> str:
    if indicator.kind == "ip" and indicator.severity == "low":
        return "benign"
    if verdict == "hot" and indicator.severity != "high":
        return "watch"
    return verdict


def _heuristic_signal_review(index: int, indicator: Indicator) -> RuntimeSignalReview:
    if indicator.severity == "high":
        verdict = "watch"
    elif indicator.kind in {"network", "domain", "ip"}:
        verdict = "watch"
    else:
        verdict = "benign"

    eu_relevance = "possible" if indicator.kind in {"network", "domain", "process"} else "none"
    if indicator.kind == "process" and indicator.severity == "high":
        note = "Shell or scripting-host signal. Verify whether this is expected behavior and whether execution can affect people or data."
    elif indicator.kind in {"network", "domain", "ip"}:
        note = "Connectivity signal. Check whether outbound communication matches declared purpose, data flows, and documentation."
    elif indicator.kind == "file":
        note = "File path signal. Confirm whether local reads/writes are expected and documented."
    else:
        note = "Low-context static signal. Review alongside use-case documentation before drawing conclusions."

    return RuntimeSignalReview(
        signal_index=index,
        worker=f"signal-worker-{index}",
        kind=indicator.kind,
        value=indicator.value,
        severity=indicator.severity,
        review_mode="heuristic",
        verdict=verdict,
        eu_ai_act_relevance=eu_relevance,
        note=note,
    )


def _clean_enum(value: str, allowed: set[str], fallback: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    return normalized if normalized in allowed else fallback


def _entropy(content: bytes) -> float:
    counts = Counter(content)
    size = len(content)
    return -sum((count / size) * math.log2(count / size) for count in counts.values())


def _file_type(content: bytes, filename: str) -> str:
    lower = filename.lower()
    if content.startswith(b"MZ"):
        return "windows-pe"
    if content.startswith(b"\x7fELF"):
        return "linux-elf"
    if content.startswith(b"#!"):
        return "script"
    if lower.endswith((".js", ".mjs", ".ts", ".tsx")):
        return "javascript"
    if lower.endswith((".py", ".sh", ".ps1", ".bat", ".cmd")):
        return "script"
    if lower.endswith((".zip", ".jar", ".war")):
        return "archive"
    if lower.endswith((".txt", ".md", ".json", ".yaml", ".yml")):
        return "text"
    return "unknown"


def _risk_score(indicators: list[Indicator], entropy: float, file_type: str) -> int:
    score = 5
    score += sum(18 for item in indicators if item.severity == "high")
    score += sum(7 for item in indicators if item.severity == "medium")
    score += sum(2 for item in indicators if item.severity == "low")
    if entropy >= 7.2:
        score += 10
    if file_type in {"windows-pe", "linux-elf"}:
        score += 8
    if file_type in {"script", "javascript"} and any(
        item.kind == "process" and item.severity == "high" for item in indicators
    ) and any(item.kind in {"network", "domain", "ip"} for item in indicators):
        score += 10
    if file_type in {"text", "javascript"} and not any(
        item.severity == "high" for item in indicators
    ):
        score = min(score, 35)
    return min(score, 100)


def _verdict(score: int) -> str:
    if score >= 75:
        return "hot"
    if score >= 45:
        return "watch"
    return "quiet"


def _runtime_analyst(
    *,
    filename: str,
    file_type: str,
    size_bytes: int,
    entropy: float,
    heuristic_score: int,
    indicators: list[Indicator],
) -> dict[str, object]:
    model = settings.runtime_analyst_model
    if model:
        try:
            return _run_llm_analyst(
                model=model,
                filename=filename,
                file_type=file_type,
                size_bytes=size_bytes,
                entropy=entropy,
                heuristic_score=heuristic_score,
                indicators=indicators,
            )
        except Exception as exc:
            logger.warning("Runtime analyst LLM call failed (%s); using heuristic.", exc)

    return {
        "mode": "heuristic",
        "basis": "Static byte/string triage. The artifact was not executed.",
        "confidence": _confidence(indicators, entropy, heuristic_score, ai_used=False),
        "risk_score": heuristic_score,
        "summary": _summary(filename, file_type, indicators, entropy, heuristic_score),
        "analysis": _analysis(indicators, entropy, heuristic_score),
    }


def _run_llm_analyst(
    *,
    model: str,
    filename: str,
    file_type: str,
    size_bytes: int,
    entropy: float,
    heuristic_score: int,
    indicators: list[Indicator],
) -> dict[str, object]:
    raw = llm_service.complete(
        model=model,
        system=_RUNTIME_ANALYST_SYSTEM,
        user=json.dumps(
            {
                "filename": filename,
                "file_type": file_type,
                "size_bytes": size_bytes,
                "entropy": round(entropy, 2),
                "heuristic_score": heuristic_score,
                "indicators": [indicator.__dict__ for indicator in indicators[:24]],
                "instruction": (
                    "Classify benign developer/product files conservatively. "
                    "An embedded URL, domain, or local path alone is not suspicious."
                ),
            },
            indent=2,
        ),
        json_mode=False,
        max_tokens=1200,
    )
    data = _parse_runtime_analyst_text(raw)
    risk_score = int(data.get("risk_score", heuristic_score))
    risk_score = max(0, min(100, risk_score))
    analysis = data.get("analysis", [])
    if not isinstance(analysis, list):
        analysis = [str(analysis)]
    summary = str(data.get("summary") or _summary(filename, file_type, indicators, entropy, risk_score))
    if not analysis:
        analysis = _analysis(indicators, entropy, risk_score)
    return {
        "mode": "ai",
        "basis": (
            "AI-assisted static triage over extracted strings, entropy, file type, and indicators. "
            "The artifact was not executed."
        ),
        "confidence": _confidence(indicators, entropy, risk_score, ai_used=True),
        "risk_score": risk_score,
        "summary": summary,
        "analysis": [str(item) for item in analysis[:6]],
    }


def _summary(
    filename: str,
    file_type: str,
    indicators: list[Indicator],
    entropy: float,
    risk_score: int,
) -> str:
    network_count = sum(item.kind in {"network", "domain", "ip"} for item in indicators)
    process_count = sum(item.kind == "process" for item in indicators)
    return (
        f"{filename} looks like {file_type}. Static inspection found {len(indicators)} indicators, "
        f"including {network_count} network indicators and {process_count} process hints. "
        f"Entropy is {entropy:.2f}; current behavioral risk score is {risk_score}/100."
    )


def _parse_runtime_analyst_text(raw: str) -> dict[str, object]:
    text = raw.strip()
    try:
        data = llm_service.parse_json(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    score_match = re.search(r"(?i)\b(?:RISK_SCORE|risk_score|score)\s*:\s*(\d{1,3})\b", text)
    summary_match = re.search(
        r"(?is)\bSUMMARY\s*:\s*(.+?)(?=\s+\b(?:NOTE|ANALYSIS)\s*\d*\s*:|$)",
        text,
    )
    note_matches = re.findall(
        r"(?is)\b(?:NOTE|ANALYSIS)\s*\d*\s*:\s*(.+?)(?=\s+\b(?:NOTE|ANALYSIS)\s*\d*\s*:|$)",
        text,
    )

    result: dict[str, object] = {}
    if score_match:
        result["risk_score"] = int(score_match.group(1))
    if summary_match:
        result["summary"] = summary_match.group(1).strip()
    if note_matches:
        result["analysis"] = [note.strip() for note in note_matches if note.strip()]
    elif not result and text:
        compact = " ".join(text.split())
        result["analysis"] = [compact[:260]]
    return result


def _confidence(
    indicators: list[Indicator],
    entropy: float,
    risk_score: int,
    *,
    ai_used: bool,
) -> str:
    if not indicators and entropy < 6.5:
        return "low"
    if ai_used and len(indicators) >= 2:
        return "medium"
    if risk_score >= 75 and len(indicators) >= 3:
        return "medium"
    return "low"


def _graph(filename: str, indicators: list[Indicator]) -> tuple[list[RuntimeNode], list[RuntimeEdge]]:
    nodes = [RuntimeNode(id="artifact", label=filename[:28], kind="artifact", severity="medium")]
    edges: list[RuntimeEdge] = []
    for index, item in enumerate(indicators[:12], start=1):
        node_id = f"signal-{index}"
        nodes.append(RuntimeNode(id=node_id, label=item.value[:32], kind=item.kind, severity=item.severity))
        edges.append(RuntimeEdge(source="artifact", target=node_id, label=item.kind))
    return nodes, edges


def _events(filename: str, indicators: list[Indicator]) -> list[RuntimeEvent]:
    events = [
        RuntimeEvent(
            time="00:00.000",
            actor="loader",
            action="fingerprinted artifact",
            target=filename,
            severity="low",
        )
    ]
    for index, item in enumerate(indicators[:10], start=1):
        events.append(
            RuntimeEvent(
                time=f"00:{index:02d}.{index * 137:03d}",
                actor=item.kind,
                action=f"observed {item.evidence.lower()}",
                target=item.value,
                severity=item.severity,
            )
        )
    return events


def _analysis(indicators: list[Indicator], entropy: float, risk_score: int) -> list[str]:
    notes: list[str] = []
    if any(item.kind in {"network", "domain", "ip"} for item in indicators):
        notes.append("Network-capable strings were found. Review whether outbound calls match the product's declared purpose.")
    if any(item.kind == "process" and item.severity == "high" for item in indicators):
        notes.append("Command shell or scripting host indicators are present. A real sandbox run should capture child process creation.")
    if any(item.kind == "file" for item in indicators):
        notes.append("Local path strings suggest file-system interaction. Confirm whether reads/writes are expected.")
    if entropy >= 7.2:
        notes.append("High byte entropy can indicate compression, packing, encryption, or bundled binary content.")
    if not notes:
        notes.append("No strong indicators were extracted from static bytes. That does not prove the artifact is safe.")
    notes.append(
        "This is static inspection, not execution. Treat it as triage before running the artifact in an isolated VM."
    )
    if risk_score >= 70:
        notes.append("Recommendation: do not execute on a workstation; use a disposable sandbox with network capture.")
    return notes


def _is_private_ip(octets: list[int]) -> bool:
    first, second = octets[0], octets[1]
    return (
        first == 10
        or first == 127
        or (first == 172 and 16 <= second <= 31)
        or (first == 192 and second == 168)
    )


def _provider_credentials_ready(provider: str) -> bool:
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider == "gemini":
        return bool(settings.gemini_api_key)
    if provider == "vllm":
        return bool(settings.vllm_base_url)
    return False


_RUNTIME_ANALYST_SYSTEM = """\
You are a runtime artifact triage analyst.

You receive static inspection data extracted from an uploaded artifact. The artifact has NOT been
executed. Your job is to reduce false positives and explain what should be checked next.

Scoring rules:
- 0-24 quiet: ordinary file, documentation, config, source, or low-risk artifact.
- 25-44 quiet but worth noting: harmless indicators such as documentation URLs or local paths.
- 45-74 watch: multiple suspicious signals or executable/script with network or shell indicators.
- 75-100 hot: strong execution risk, command shell plus network, suspicious binary, packed executable, or dangerous intent.

Be conservative. Do not treat clean files as suspicious only because they contain URLs, domains,
developer commands, localhost/private IPs, paths, or common words. Static indicators are clues, not proof.

Return exactly this plain text format, with no markdown:
RISK_SCORE: <0-100 integer>
SUMMARY: <one concise paragraph>
NOTE: <short analyst note>
NOTE: <short analyst note>
NOTE: <short analyst note>\
"""


_SIGNAL_REVIEW_SYSTEM = """\
You are a capped signal-review worker for an EU AI Act artifact triage tool.

You receive extracted static signals from one uploaded artifact. The artifact has NOT been executed.
Review each signal independently. Keep false positives low. A normal URL, path, or developer command
is not automatically suspicious. Tie EU AI Act relevance to whether the signal suggests AI behavior,
affected-person impact, external data flow, transparency, or governance questions.

For each signal, return exactly this plain text block:
SIGNAL <number>
VERDICT: benign|watch|hot
EU_AI_ACT: none|possible|likely
NOTE: <one short sentence>

No markdown. No extra sections.\
"""
