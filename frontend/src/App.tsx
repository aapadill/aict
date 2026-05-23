import React, { useEffect, useState } from "react";
import CaseDashboard from "./components/CaseDashboard";
import CaseWorkspace from "./components/CaseWorkspace";

type Theme = "light" | "dark";
type Page = "home" | "board";

function getInitialTheme(): Theme {
  const stored = window.localStorage.getItem("aict-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [openCaseId, setOpenCaseId] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("home");
  const [theme, setTheme] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("aict-theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((current) => current === "dark" ? "light" : "dark");
  const openBoard = () => {
    setOpenCaseId(null);
    setPage("board");
  };
  const openHome = () => {
    setOpenCaseId(null);
    setPage("home");
  };
  const openCase = (caseId: string) => {
    setOpenCaseId(caseId);
    setPage("board");
  };

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand-block brand-button" onClick={openHome} type="button">
          <div className="brand-mark">§</div>
          <div>
            <h1>aict</h1>
            <span className="crumbs">
              {openCaseId
                ? <>Case <span className="mono">{openCaseId}</span></>
                : page === "board"
                  ? "Cases board"
                  : "EU AI Act compliance workspace"}
            </span>
          </div>
        </button>
        <div className="topbar-meta">
          <nav className="topbar-nav" aria-label="Primary navigation">
            <button
              className={page === "home" && !openCaseId ? "active" : ""}
              type="button"
              onClick={openHome}
            >
              Home
            </button>
            <button
              className={page === "board" || openCaseId ? "active" : ""}
              type="button"
              onClick={openBoard}
            >
              Board
            </button>
          </nav>
          <button
            className="theme-toggle"
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "white" : "dark"} mode`}
            title={`Switch to ${theme === "dark" ? "white" : "dark"} mode`}
          >
            <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
          </button>
        </div>
      </header>
      <div className="limitation">
        This is a decision-support draft, not final legal advice.
      </div>
      <main className="main">
        {openCaseId ? (
          <CaseWorkspace caseId={openCaseId} onBack={openBoard} />
        ) : page === "board" ? (
          <CaseDashboard onOpen={openCase} />
        ) : (
          <HomeLanding onOpenBoard={openBoard} />
        )}
      </main>
    </div>
  );
}

function HomeLanding({ onOpenBoard }: { onOpenBoard: () => void }) {
  return (
    <div className="landing">
      <section className="landing-hero">
        <div>
          <div className="eyebrow">EU AI Act compliance assistant</div>
          <h2>aict helps teams turn AI use-case documents into a grounded first-pass review.</h2>
          <p>
            Upload product notes, governance material, and supporting evidence. aict extracts the
            case facts, checks likely AI Act scope and risk signals, maps obligations, and keeps
            citations tied to stored source chunks.
          </p>
          <div className="landing-actions">
            <button className="primary" onClick={onOpenBoard} type="button">
              Open cases board
            </button>
          </div>
        </div>
        <div className="landing-panel">
          <h3>Built for review sessions</h3>
          <ul>
            <li>Collect the use-case description and uploaded evidence.</li>
            <li>Run a cited first-pass AI Act assessment.</li>
            <li>Track missing facts, uncertainties, and follow-up questions.</li>
            <li>Continue in chat without losing source grounding.</li>
          </ul>
        </div>
      </section>

      <section className="landing-strip">
        <div>
          <strong>Document grounded</strong>
          <span>Findings are linked to uploaded files and local reference chunks.</span>
        </div>
        <div>
          <strong>Hackathon simple</strong>
          <span>Local JSON storage, lightweight retrieval, and clear reports.</span>
        </div>
        <div>
          <strong>Decision support</strong>
          <span>Designed to surface questions, not replace legal review.</span>
        </div>
      </section>
    </div>
  );
}
