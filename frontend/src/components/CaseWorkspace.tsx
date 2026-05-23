import React, { useEffect, useState } from "react";
import {
  getAnalysis,
  getCase,
  listDocuments,
  runAnalysis,
  updateCase,
} from "../api/client";
import type { AnalysisResult, Case, DocumentRecord } from "../types/api";
import DocumentUploader from "./DocumentUploader";
import AnalysisReport from "./AnalysisReport";
import ChatPanel from "./ChatPanel";
import EmptyState from "./EmptyState";
import LoadingButton from "./LoadingButton";
import { buildMarkdownReport, downloadMarkdown } from "../utils/exportReport";

type Tab = "report" | "chat";

const TAB_LABELS: Record<Tab, string> = {
  report: "Report",
  chat: "Chat",
};

export default function CaseWorkspace({
  caseId,
  onBack,
}: {
  caseId: string;
  onBack: () => void;
}) {
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [tab, setTab] = useState<Tab>("report");
  const [error, setError] = useState<string | null>(null);
  const [loadingCase, setLoadingCase] = useState(true);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [running, setRunning] = useState(false);
  const [copying, setCopying] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [caseDescription, setCaseDescription] = useState("");
  const [savingCase, setSavingCase] = useState(false);

  const loadAll = async () => {
    setError(null);
    setLoadingCase(true);
    try {
      const c = await getCase(caseId);
      setCaseData(c);
      setCaseDescription(c.description ?? "");
      if (c.documents) setDocuments(c.documents);
      else {
        const docs = await listDocuments(caseId);
        setDocuments(docs);
      }
    } catch (e: any) {
      setError(e?.message ?? "Failed to load case");
    } finally {
      setLoadingCase(false);
    }
    setLoadingAnalysis(true);
    try {
      const a = await getAnalysis(caseId);
      setAnalysis(a);
    } catch (e: any) {
      // 404 likely means no analysis yet — keep null
      if (!/404/.test(String(e?.message))) {
        setError((prev) => prev ?? (e?.message ?? "Failed to load analysis"));
      }
      setAnalysis(null);
    } finally {
      setLoadingAnalysis(false);
    }
  };

  useEffect(() => {
    loadAll();
     
  }, [caseId]);

  useEffect(() => {
    if (!analysis && tab === "chat") {
      setTab("report");
    }
  }, [analysis, tab]);

  const persistCaseDescription = async () => {
    if (!caseData || caseDescription.trim() === (caseData.description ?? "")) return caseData;
    setSavingCase(true);
    try {
      const updated = await updateCase(caseId, { description: caseDescription.trim() });
      setCaseData(updated);
      return updated;
    } finally {
      setSavingCase(false);
    }
  };

  const generatedTitle = (a: AnalysisResult): string => {
    const factTitle = a.extracted_facts.find((fact) => fact.label === "Purpose")?.value;
    const source = factTitle || a.summary || "AI Act review";
    const compact = source
      .replace(/^likely purpose:\s*/i, "")
      .replace(/^the\s+/i, "")
      .replace(/\s+/g, " ")
      .trim();
    if (!compact) return "AI Act review";
    return compact.length > 72 ? `${compact.slice(0, 69).replace(/[ ,;:]+$/, "")}...` : compact;
  };

  const handleSaveDescription = async () => {
    setError(null);
    try {
      await persistCaseDescription();
    } catch (e: any) {
      setError(e?.message ?? "Failed to save description");
    }
  };

  const handleRunAnalysis = async () => {
    setRunning(true);
    setError(null);
    try {
      await persistCaseDescription();
      const a = await runAnalysis(caseId);
      setAnalysis(a);
      const nextTitle = generatedTitle(a);
      const updated = await updateCase(caseId, { title: nextTitle });
      setCaseData(updated);
      setTab("report");
    } catch (e: any) {
      setError(e?.message ?? "Analysis failed");
    } finally {
      setRunning(false);
    }
  };

  const handleCopy = async () => {
    if (!analysis) return;
    setCopying(true);
    try {
      const md = buildMarkdownReport(analysis, caseData?.title);
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(md);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = md;
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(textarea);
        if (!copied) throw new Error("Clipboard API is unavailable");
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch (e: any) {
      setError(e?.message ?? "Copy failed");
    } finally {
      setCopying(false);
    }
  };

  const handleDownload = async () => {
    if (!analysis) return;
    setExporting(true);
    try {
      const md = buildMarkdownReport(analysis, caseData?.title);
      downloadMarkdown(`ai-act-assessment-${caseId}.md`, md);
    } catch (e: any) {
      setError(e?.message ?? "Download failed");
    } finally {
      setExporting(false);
    }
  };

  const handleUploaded = (newDocs: DocumentRecord[]) => {
    if (analysis) return;
    setDocuments((current) => {
      const existing = new Set(current.map((doc) => doc.id));
      return [
        ...current,
        ...newDocs.filter((doc) => !existing.has(doc.id)),
      ];
    });
    setAnalysis(null);
  };

  const handleReassessFromChat = async () => {
    await handleRunAnalysis();
    setTab("report");
  };

  const intakeLocked = Boolean(analysis);
  const savedDescription = caseData?.description?.trim() ?? "";
  const currentDescription = caseDescription.trim();
  const descriptionChanged = currentDescription !== savedDescription;
  const descriptionReady = Boolean(savedDescription) && !descriptionChanged;
  const canSaveDescription = !intakeLocked && Boolean(currentDescription) && descriptionChanged;
  const descriptionActionLabel = intakeLocked
    ? "Locked"
    : "Save";
  const descriptionStatus = savingCase
    ? "Saving..."
    : intakeLocked
      ? "Locked after analysis."
      : descriptionReady
        ? "Description saved. You can edit it before analysis."
        : "Describe the system before adding files.";
  const readyForAnalysis = documents.length > 0 && descriptionReady;
  const headerDescription = analysis ? caseData?.description : null;

  const tabItems: { id: Tab; label: string; meta: string }[] = [
    { id: "report", label: TAB_LABELS.report, meta: analysis ? "Ready" : "Draft" },
    { id: "chat", label: TAB_LABELS.chat, meta: analysis ? "Ask" : "Locked" },
  ];

  if (loadingCase && !caseData) {
    return <div className="card"><span className="spinner" /> Loading case…</div>;
  }
  if (!caseData) {
    return (
      <div className="card">
        <div className="error-banner">{error ?? "Case not found"}</div>
        <button onClick={onBack}>← Back to cases</button>
      </div>
    );
  }

  return (
    <div className="workspace-page">
      <div className="workspace-hero">
        <button className="ghost back-button" onClick={onBack}>Cases</button>
        <div className="workspace-head">
          <div className="title-block">
            <div className="eyebrow">Compliance review</div>
            <h1>{caseData.title}</h1>
            {headerDescription && <p>{headerDescription}</p>}
            <div className="workspace-meta">
              <span>Created {new Date(caseData.created_at).toLocaleString()}</span>
              <span>{documents.length} document{documents.length === 1 ? "" : "s"}</span>
              <span className={`badge ${analysis ? "parsed" : ""}`}>
                {analysis ? "analysis ready" : "no analysis"}
              </span>
            </div>
          </div>
          <div className="actions">
            <LoadingButton
              loading={copying}
              loadingText="Copying…"
              onClick={handleCopy}
              disabled={!analysis}
            >
              {copied ? "Copied" : "Copy Markdown"}
            </LoadingButton>
            <LoadingButton
              loading={exporting}
              loadingText="Exporting…"
              onClick={handleDownload}
              disabled={!analysis}
            >
              Download .md
            </LoadingButton>
          </div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="workspace-grid">
        <aside className="workspace-rail">
          {!intakeLocked && (
            <div className="panel intake-panel">
              <div className="section-head compact-head">
                <div>
                  <h2>Use-case description</h2>
                  <p>{descriptionStatus}</p>
                </div>
              </div>
              <textarea
                value={caseDescription}
                onChange={(event) => setCaseDescription(event.target.value)}
                placeholder="Example: An AI assistant screens job applications, summarizes CVs, ranks candidates, and supports recruiter review."
              />
              <div className="intake-actions">
                <LoadingButton
                  className="compact"
                  loading={savingCase}
                  loadingText="Saving..."
                  onClick={handleSaveDescription}
                  disabled={!canSaveDescription}
                >
                  {descriptionActionLabel}
                </LoadingButton>
              </div>
            </div>
          )}
          <DocumentUploader
            caseId={caseId}
            documents={documents}
            onUploaded={handleUploaded}
            locked={intakeLocked}
          />
          <div className="panel case-summary">
            <h2>Case status</h2>
            <div className="metric-row">
              <span>Documents</span>
              <strong>{documents.length}</strong>
            </div>
            <div className="metric-row">
              <span>Citations</span>
              <strong>{analysis?.citations.length ?? 0}</strong>
            </div>
            <div className="metric-row">
              <span>Open questions</span>
              <strong>{analysis?.follow_up_questions.length ?? 0}</strong>
            </div>
            <div className="metric-row">
              <span>Trace events</span>
              <strong>{analysis?.agent_trace.length ?? 0}</strong>
            </div>
          </div>
        </aside>

        <section className="workspace-main">
          <div className="tabs" role="tablist" aria-label="Case workspace">
            {tabItems.map((item) => (
              <button
                key={item.id}
                role="tab"
                aria-selected={tab === item.id}
                disabled={item.id === "chat" && !analysis}
                className={tab === item.id ? "active" : ""}
                onClick={() => setTab(item.id)}
              >
                <span>{item.label}</span>
                <small>{item.meta}</small>
              </button>
            ))}
          </div>

          <div className="tab-panel" role="tabpanel" aria-label={TAB_LABELS[tab]}>
            {tab === "report" && (
              loadingAnalysis ? (
                <div className="panel"><span className="spinner" /> Loading analysis…</div>
              ) : analysis ? (
                <AnalysisReport a={analysis} onOpenChat={() => setTab("chat")} />
              ) : (
                <EmptyState
                  icon="◷"
                  title="No analysis yet"
                  hint={!descriptionReady
                    ? "Add the use-case description, upload at least one document, then run analysis."
                    : documents.length === 0
                      ? "Upload at least one document, then run analysis."
                      : "Click Run analysis to generate an AI Act assessment."}
                  action={
                    <LoadingButton
                      className="primary"
                      loading={running}
                      loadingText="Analyzing…"
                      onClick={handleRunAnalysis}
                      disabled={!readyForAnalysis}
                    >
                      Run analysis
                    </LoadingButton>
                  }
                />
              )
            )}

            {tab === "chat" && (
              <ChatPanel
                caseId={caseId}
                reassessing={running}
                onReassessRequested={handleReassessFromChat}
              />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
