import React, { useEffect, useState } from "react";
import CaseDashboard from "./components/CaseDashboard";
import CaseWorkspace from "./components/CaseWorkspace";
import RuntimeInspector from "./components/RuntimeInspector";
import { API_BASE_URL, getApiMode, onApiModeChange } from "./api/client";

export default function App() {
  const [openCaseId, setOpenCaseId] = useState<string | null>(null);
  const [view, setView] = useState<"cases" | "runtime">("runtime");
  const [mode, setMode] = useState(getApiMode());

  useEffect(() => onApiModeChange(setMode), []);

  return (
    <div className={`app ${view === "runtime" ? "runtime-app" : ""}`}>
      <header className="topbar">
        <div className="row" style={{ gap: 10 }}>
          <h1>{view === "runtime" ? "Runtime Trace Lab" : "AI Act Compliance Assistant"}</h1>
          <span className="crumbs small">
            {view === "runtime" ? "/ artifact cockpit" : openCaseId ? <>/ case <span className="mono">{openCaseId}</span></> : "/ cases"}
          </span>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button className={view === "runtime" ? "primary" : ""} onClick={() => { setView("runtime"); setOpenCaseId(null); }}>
            Runtime
          </button>
          <button className={view === "cases" ? "primary" : ""} onClick={() => setView("cases")}>
            Cases
          </button>
          <span className="small faint">API: <span className="mono">{API_BASE_URL}</span></span>
          <span className={`status-pill ${mode === "mock" ? "mock" : ""}`}>
            {mode === "mock" && view !== "runtime" ? "Mock fallback" : "Live"}
          </span>
        </div>
      </header>
      {view === "cases" && (
        <div className="limitation">
          This is a decision-support draft, not final legal advice.
        </div>
      )}
      <main className="main">
        {view === "runtime" ? (
          <RuntimeInspector />
        ) : openCaseId ? (
          <CaseWorkspace caseId={openCaseId} onBack={() => setOpenCaseId(null)} />
        ) : (
          <CaseDashboard onOpen={setOpenCaseId} />
        )}
      </main>
    </div>
  );
}
