import React, { useEffect, useState } from "react";
import {
  ArrowRight,
  FileSearch,
  Files,
  History,
  Home,
  LayoutDashboard,
  MessageSquare,
  Moon,
  Scale,
  ShieldCheck,
  Sun,
} from "lucide-react";
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
  const productRows = [
    ["Purpose", "found", "Candidate screening and ranking", "Verified from product brief"],
    ["Risk", "high", "Employment signal detected", "Annex III review suggested"],
    ["Evidence", "found", "12 verified citations", "Uploaded docs + reference corpus"],
    ["Open facts", "medium", "Provider role, validation, monitoring", "Questions queued for review"],
  ];

  return (
    <div className="landing">
      <section className="landing-hero">
        <div className="landing-hero-top">
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

          <div className="landing-stack" aria-hidden="true">
            <div className="stack-paper primary-paper">
              <span>Use-case brief</span>
              <strong>HR screening assistant</strong>
              <em>purpose, outputs, users, oversight</em>
            </div>
            <div className="stack-paper secondary-paper">
              <span>Reference corpus</span>
              <strong>AI Act extracts</strong>
              <em>scope, risk areas, obligations</em>
            </div>
            <div className="stack-paper tertiary-paper">
              <span>Report snapshot</span>
              <strong>Likely high-risk</strong>
              <em>citations verified</em>
            </div>
          </div>
        </div>

        <div className="landing-product" aria-label="aict workflow preview">
          <div className="product-sidebar">
            <div className="product-logo"><StackedLogo size={14} /> aict</div>
            {[
              ["Intake", ""],
              ["Review", "active"],
              ["Timeline", ""],
              ["Chat", ""],
            ].map(([label, active]) => (
              <div key={label} className={`product-nav ${active}`}>{label}</div>
            ))}
          </div>
          <div className="product-main">
            <div className="product-toolbar">
              <span>Compliance review</span>
              <span className="product-pill">Draft</span>
            </div>
            {productRows.map(([label, tone, text, note]) => (
              <div key={label} className="product-row">
                <span className={`product-dot ${tone}`} />
                <div>
                  <strong>{label}</strong>
                  <p>{text}</p>
                </div>
                <small>{note}</small>
              </div>
            ))}
            <div className="product-evidence">
              <div>
                <span>citation verifier</span>
                <strong>chunk_9f2c... accepted</strong>
              </div>
              <div>
                <span>open question</span>
                <strong>Who is the provider?</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="landing-divider" />

      <section className="landing-feature-intro">
        <div className="eyebrow">Built for fast first-pass reviews</div>
        <h2>Less copy-paste. More traceable reasoning.</h2>
        <p>
          The home flow mirrors the app: collect source material, extract case facts, classify
          risk signals, and keep the output easy to challenge.
        </p>
      </section>

      <section className="landing-features">
        {[
          {
            icon: Files,
            title: "Document grounded",
            desc: "Upload product briefs, vendor notes, governance docs, and case evidence. The report stays tied to those uploaded sources.",
            graphic: "docs",
          },
          {
            icon: Scale,
            title: "Decision support",
            desc: "The output is framed as a structured review: likely scope, risk signals, roles, obligations, uncertainties, and follow-up questions.",
            graphic: "risk",
          },
          {
            icon: ShieldCheck,
            title: "Citation checked",
            desc: "Generated citations are resolved against stored chunks before display, so fake references can be stripped instead of trusted.",
            graphic: "verify",
          },
        ].map((feature) => (
          <div key={feature.title} className="landing-feature">
            <div className={`feature-visual ${feature.graphic}`}>
              {feature.graphic === "docs" && (
                <>
                  <span />
                  <span />
                  <span />
                </>
              )}
              {feature.graphic === "risk" && (
                <>
                  <span className="high" />
                  <span className="medium" />
                  <span className="low" />
                  <span className="base" />
                </>
              )}
              {feature.graphic === "verify" && (
                <>
                  <span />
                  <span />
                  <span />
                </>
              )}
            </div>
            <feature.icon size={24} />
            <strong>{feature.title}</strong>
            <span>{feature.desc}</span>
          </div>
        ))}
      </section>

      <div className="landing-divider" />

      <section className="landing-proof">
        <blockquote>
          “A useful AI Act draft should show what it knows, what it cannot prove, and which source
          text supports each claim.”
        </blockquote>
        <div className="proof-grid">
          <div>
            <FileSearch size={18} />
            <span>Source snippets stay visible</span>
          </div>
          <div>
            <History size={18} />
            <span>Report versions remain in the timeline</span>
          </div>
          <div>
            <MessageSquare size={18} />
            <span>Follow-up chat starts from the saved assessment</span>
          </div>
        </div>
      </section>

      <div className="landing-divider" />

      <section className="landing-cta">
        <h2>Start with the documents you already have.</h2>
        <p>Create a case, add the use-case description and supporting files, then run the first-pass review.</p>
        <button className="primary" onClick={onOpenBoard} type="button">
          Open cases board <ArrowRight size={15} />
        </button>
      </section>
    </div>
  );
}
