import React, { useEffect, useState } from "react";
import CaseDashboard from "./components/CaseDashboard";
import CaseWorkspace from "./components/CaseWorkspace";
import { API_BASE_URL, checkHealth, getApiMode, onApiModeChange } from "./api/client";

export default function App() {
  const [openCaseId, setOpenCaseId] = useState<string | null>(null);
  const [mode, setMode] = useState(getApiMode());
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);

  useEffect(() => onApiModeChange(setMode), []);

  useEffect(() => {
    checkHealth()
      .then((h) => setLlmConfigured(h.llm_configured))
      .catch(() => setLlmConfigured(null)); // backend unreachable — don't show banner
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="row" style={{ gap: 10 }}>
          <h1>AI Act Compliance Assistant</h1>
          <span className="crumbs small">
            {openCaseId ? <>/ case <span className="mono">{openCaseId}</span></> : "/ cases"}
          </span>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <span className="small faint">API: <span className="mono">{API_BASE_URL}</span></span>
          <span className={`status-pill ${mode === "mock" ? "mock" : ""}`}>
            {mode === "mock" ? "Mock fallback" : "Live"}
          </span>
        </div>
      </header>
      <div className="limitation">
        This is a decision-support draft, not final legal advice.
      </div>
      {llmConfigured === false && (
        <div className="llm-setup-banner">
          <strong>⚠ LLM not configured — analysis will not run.</strong>
          <span>
            {" "}Set per-agent model variables in your <code>.env</code> file and restart the backend.
            See <code>.env.example</code> for provider options (vllm, anthropic, openai).
          </span>
          <details style={{ marginTop: 6 }}>
            <summary style={{ cursor: "pointer" }}>Show required variables</summary>
            <pre>{[
              "VLLM_BASE_URL=http://your-server:8000/v1",
              "VLLM_API_KEY=your-key",
              "DOCUMENT_FACT_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "AI_SYSTEM_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "RISK_CLASSIFICATION_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "OBLIGATIONS_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "CRITIC_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "CHAT_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
            ].join("\n")}</pre>
          </details>
        </div>
      )}
      <main className="main">
        {openCaseId ? (
          <CaseWorkspace caseId={openCaseId} onBack={() => setOpenCaseId(null)} />
        ) : (
          <CaseDashboard onOpen={setOpenCaseId} />
        )}
      </main>
    </div>
  );
}
