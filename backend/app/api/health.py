from fastapi import APIRouter

from app.agents.workflow import llm_configured

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_configured": llm_configured()}
