from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.cases import router as cases_router
from app.api.health import router as health_router
from app.api.runtime import router as runtime_router
from app.core.config import settings
from app.storage import initialize_storage


def create_app() -> FastAPI:
    settings.ensure_dirs()
    initialize_storage()

    app = FastAPI(
        title="AI Act Compliance Assistant",
        description=(
            "Local-first backend for running a cited first-pass EU AI Act assessment. "
            "Output is decision support, not final legal advice."
        ),
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(cases_router)
    app.include_router(runtime_router)
    return app


app = create_app()
