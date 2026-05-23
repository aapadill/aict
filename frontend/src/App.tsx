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
        <div className="brand-block">
          <div className="brand-mark">§</div>
          <div>
            <h1>aict</h1>
            <span className="crumbs">
              {openCaseId
                ? <>Case <span className="mono">{openCaseId}</span></>
                : "EU AI Act compliance workspace"}
            </span>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="api-pill">API <span className="mono">{API_BASE_URL}</span></span>
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
