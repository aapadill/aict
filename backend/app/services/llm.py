from __future__ import annotations

import json
import re
from typing import Any


def complete(
    model: str,
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    max_tokens: int = 2048,
) -> str:
    """Call an LLM provider and return the response text.

    ``model`` must be ``provider:model-id``, e.g.
    ``anthropic:claude-haiku-4-5-20251001``, ``openai:gpt-4o-mini``,
    or ``gemini:gemini-2.5-flash``.

    When ``json_mode=True`` the response is expected to be valid JSON.
    For Anthropic the instruction is embedded in the system prompt; for
    OpenAI ``response_format`` is set to ``json_object``.
    """
    if not model or ":" not in model:
        raise ValueError(
            f"Invalid model string: {model!r}. "
            "Expected 'provider:model-id', e.g. 'anthropic:claude-haiku-4-5-20251001'."
        )
    provider, model_id = model.split(":", 1)
    if provider == "anthropic":
        return _call_anthropic(model_id, system, user, json_mode=json_mode, max_tokens=max_tokens)
    if provider == "openai":
        return _call_openai(model_id, system, user, json_mode=json_mode, max_tokens=max_tokens)
    if provider == "gemini":
        return _call_gemini(model_id, system, user, json_mode=json_mode, max_tokens=max_tokens)
    if provider == "vllm":
        return _call_vllm(model_id, system, user, json_mode=json_mode, max_tokens=max_tokens)
    raise ValueError(
        f"Unknown LLM provider: {provider!r}. Supported: anthropic, openai, gemini, vllm."
    )


def parse_json(text: str) -> Any:
    """Parse JSON from a model response, stripping Markdown fences if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```$", "", stripped.rstrip())
    return json.loads(stripped)


def _call_anthropic(
    model_id: str,
    system: str,
    user: str,
    *,
    json_mode: bool,
    max_tokens: int,
) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError("Install the 'anthropic' package: pip install anthropic") from exc

    from app.core.config import settings  # late import avoids circular refs at startup

    sys_prompt = system
    if json_mode:
        sys_prompt = (
            sys_prompt
            + "\n\nRespond with valid JSON only. "
            "Do not include markdown fences, prose, or any text outside the JSON object."
        )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        system=sys_prompt,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _call_openai(
    model_id: str,
    system: str,
    user: str,
    *,
    json_mode: bool,
    max_tokens: int,
) -> str:
    try:
        import openai
    except ImportError as exc:
        raise ImportError("Install the 'openai' package: pip install openai") from exc

    from app.core.config import settings  # late import avoids circular refs at startup

    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    client = openai.OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _call_gemini(
    model_id: str,
    system: str,
    user: str,
    *,
    json_mode: bool,
    max_tokens: int,
) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise ImportError("Install the 'google-genai' package: pip install google-genai") from exc

    from app.core.config import settings  # late import avoids circular refs at startup

    prompt = f"{system}\n\nUser input:\n{user}"
    config_kwargs: dict[str, Any] = {"max_output_tokens": max_tokens}
    if json_mode:
        prompt += (
            "\n\nRespond with valid JSON only. "
            "Do not include markdown fences, prose, or any text outside the JSON object."
        )
        config_kwargs["response_mime_type"] = "application/json"

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text or ""


def _call_vllm(
    model_id: str,
    system: str,
    user: str,
    *,
    json_mode: bool,
    max_tokens: int,
) -> str:
    """Call a vLLM server via its OpenAI-compatible API."""
    try:
        import openai
    except ImportError as exc:
        raise ImportError("Install the 'openai' package: pip install openai") from exc

    from app.core.config import settings  # late import avoids circular refs at startup

    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    # vLLM supports json_object mode; embed the instruction in the system prompt as well
    # to be safe with models that may not fully honour the response_format parameter.
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
        kwargs["messages"][0]["content"] = (
            system
            + "\n\nRespond with valid JSON only. "
            "Do not include markdown fences, prose, or any text outside the JSON object."
        )

    client = openai.OpenAI(
        api_key=settings.vllm_api_key,
        base_url=settings.vllm_base_url,
    )
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content
