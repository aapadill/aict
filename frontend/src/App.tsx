import React, { useEffect, useState } from "react";
import { ArrowRight, Files, Home, LayoutDashboard, Moon, Scale, ShieldCheck, Sun } from "lucide-react";
import CaseDashboard from "./components/CaseDashboard";
import CaseWorkspace from "./components/CaseWorkspace";
import StackedLogo from "./components/StackedLogo";

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
          <div className="brand-mark"><StackedLogo size={18} /></div>
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
              <Home size={14} /> Home
            </button>
            <button
              className={page === "board" || openCaseId ? "active" : ""}
              type="button"
              onClick={openBoard}
            >
              <LayoutDashboard size={14} /> Board
            </button>
          </nav>
          <button
            className="theme-toggle"
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "white" : "dark"} mode`}
            title={`Switch to ${theme === "dark" ? "white" : "dark"} mode`}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </header>
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
        <div className="landing-copy">
          <div className="eyebrow">EU AI Act compliance assistant</div>
          <h2>aict helps teams turn AI use-case documents into a grounded first-pass review.</h2>
          <p>
            Upload product notes, governance material, and supporting evidence. aict extracts the
            case facts, checks likely AI Act scope and risk signals, maps obligations, and keeps
            citations tied to stored source chunks.
          </p>
          <div className="landing-actions">
            <button className="primary" onClick={onOpenBoard} type="button">
              Open cases board <ArrowRight size={15} />
            </button>
          </div>
        </div>

        <div className="landing-product" aria-label="aict workflow preview">
          <div className="product-sidebar">
            <div className="product-logo"><StackedLogo size={14} /> aict</div>
            {[
              ["Review", "active"],
              ["Sources", ""],
              ["Report", ""],
              ["Chat", ""],
            ].map(([label, active]) => (
              <div key={label} className={`product-nav ${active}`}>{label}</div>
            ))}
          </div>
          <div className="product-main">
            <div className="product-toolbar">
              <span>Assessment queue</span>
              <span className="product-pill">Draft</span>
            </div>
            {[
              ["Purpose", "found", "Candidate screening and ranking"],
              ["Risk", "high", "Employment signal detected"],
              ["Evidence", "found", "12 verified citations"],
              ["Open facts", "medium", "Provider role, validation, monitoring"],
            ].map(([label, tone, text]) => (
              <div key={label} className="product-row">
                <span className={`product-dot ${tone}`} />
                <div>
                  <strong>{label}</strong>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="landing-strip">
        <div>
          <Files size={18} />
          <strong>Document grounded</strong>
          <span>Findings are linked to uploaded files and local reference chunks.</span>
        </div>
        <div>
          <Scale size={18} />
          <strong>Decision support</strong>
          <span>Designed to surface questions, not replace legal review.</span>
        </div>
        <div>
          <ShieldCheck size={18} />
          <strong>Citation checked</strong>
          <span>Generated citations are verified against stored chunks before display.</span>
        </div>
      </section>
    </div>
  );
}
