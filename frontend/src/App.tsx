import React, { useEffect, useState } from "react";
import CaseDashboard from "./components/CaseDashboard";
import CaseWorkspace from "./components/CaseWorkspace";
import { API_BASE_URL, getApiMode, onApiModeChange } from "./api/client";

export default function App() {
  const [openCaseId, setOpenCaseId] = useState<string | null>(null);
  const [mode, setMode] = useState(getApiMode());

  useEffect(() => onApiModeChange(setMode), []);

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
