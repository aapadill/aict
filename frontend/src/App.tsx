import React, { useEffect, useState } from "react";
import CaseDashboard from "./components/CaseDashboard";
import CaseWorkspace from "./components/CaseWorkspace";
import { API_BASE_URL, getApiMode, onApiModeChange } from "./api/client";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  const stored = window.localStorage.getItem("aict-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [openCaseId, setOpenCaseId] = useState<string | null>(null);
  const [mode, setMode] = useState(getApiMode());
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => onApiModeChange(setMode), []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("aict-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((current) => current === "dark" ? "light" : "dark");

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
          <button
            className="theme-toggle"
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "white" : "dark"} mode`}
            title={`Switch to ${theme === "dark" ? "white" : "dark"} mode`}
          >
            <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
          </button>
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
