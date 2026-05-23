import os

# Force deterministic heuristic fallback for all tests.
# These assignments run before any app module is imported, so the Settings
# instance reads mock mode and empty model strings regardless of what .env
# has configured for the real runtime.
os.environ["LLM_PROVIDER"] = "mock"
for _var in (
    "DOCUMENT_FACT_AGENT_MODEL",
    "AI_SYSTEM_AGENT_MODEL",
    "RISK_CLASSIFICATION_AGENT_MODEL",
    "OBLIGATIONS_AGENT_MODEL",
    "CRITIC_AGENT_MODEL",
    "CHAT_AGENT_MODEL",
):
    os.environ[_var] = ""
