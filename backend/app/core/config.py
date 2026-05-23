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
    sqlite_path: Path = field(
        default_factory=lambda: _resolve(os.getenv("SQLITE_PATH", "backend/data/app.db"))
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
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "local")
    )

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.upload_dir,
            self.extracted_dir,
            self.index_dir,
            self.ai_act_corpus_dir,
            self.sqlite_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
