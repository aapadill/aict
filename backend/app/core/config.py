from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]

for env_path in (REPO_ROOT / ".env", BACKEND_ROOT / ".env"):
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


@dataclass(frozen=True)
class Settings:
    backend_host: str = field(default_factory=lambda: os.getenv("BACKEND_HOST", "127.0.0.1"))
    backend_port: int = field(default_factory=lambda: int(os.getenv("BACKEND_PORT", "8000")))
    cors_origins: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
            )
        )
    )
    data_dir: Path = field(default_factory=lambda: _resolve(os.getenv("DATA_DIR", "backend/data")))
    state_dir: Path = field(
        default_factory=lambda: _resolve(os.getenv("STATE_DIR", "backend/data/state"))
    )
    upload_dir: Path = field(
        default_factory=lambda: _resolve(os.getenv("UPLOAD_DIR", "backend/data/uploads"))
    )
    extracted_dir: Path = field(
        default_factory=lambda: _resolve(os.getenv("EXTRACTED_DIR", "backend/data/extracted"))
    )
    index_dir: Path = field(
        default_factory=lambda: _resolve(os.getenv("INDEX_DIR", "backend/data/index"))
    )
    ai_act_corpus_dir: Path = field(
        default_factory=lambda: _resolve(os.getenv("AI_ACT_CORPUS_DIR", "backend/data/corpus"))
    )
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    vllm_base_url: str = field(
        default_factory=lambda: os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    )
    vllm_api_key: str = field(default_factory=lambda: os.getenv("VLLM_API_KEY", ""))
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "local")
    )
    # Per-agent model strings: "provider:model-id" (e.g. "openai:gpt-4o-mini").
    # Leave empty to use the deterministic heuristic fallback.
    document_fact_agent_model: str = field(
        default_factory=lambda: os.getenv("DOCUMENT_FACT_AGENT_MODEL", "")
    )
    ai_system_agent_model: str = field(
        default_factory=lambda: os.getenv("AI_SYSTEM_AGENT_MODEL", "")
    )
    risk_classification_agent_model: str = field(
        default_factory=lambda: os.getenv("RISK_CLASSIFICATION_AGENT_MODEL", "")
    )
    obligations_agent_model: str = field(
        default_factory=lambda: os.getenv("OBLIGATIONS_AGENT_MODEL", "")
    )
    critic_agent_model: str = field(
        default_factory=lambda: os.getenv("CRITIC_AGENT_MODEL", "")
    )
    chat_agent_model: str = field(
        default_factory=lambda: os.getenv("CHAT_AGENT_MODEL", "")
    )

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.state_dir,
            self.upload_dir,
            self.extracted_dir,
            self.index_dir,
            self.ai_act_corpus_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
