import React, { useEffect, useState } from "react";
import {
  getAnalysis,
  getCase,
  listDocuments,
  runAnalysis,
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

  const loadAll = async () => {
    setError(null);
    setLoadingCase(true);
    try {
      const c = await getCase(caseId);
      setCaseData(c);
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

  const handleRunAnalysis = async () => {
    setRunning(true);
    setError(null);
    try {
      const a = await runAnalysis(caseId);
      setAnalysis(a);
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
      await navigator.clipboard.writeText(md);
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
    } finally {
      setExporting(false);
    }
  };

  const tabItems: { id: Tab; label: string; meta: string }[] = [
    { id: "report", label: TAB_LABELS.report, meta: analysis ? "Ready" : "Draft" },
    { id: "chat", label: TAB_LABELS.chat, meta: "Ask" },
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
            {caseData.description && <p>{caseData.description}</p>}
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
              className="primary"
              loading={running}
              loadingText="Analyzing…"
              onClick={handleRunAnalysis}
              disabled={documents.length === 0}
              title={documents.length === 0 ? "Upload at least one document first" : "Run AI Act analysis"}
            >
              Run analysis
            </LoadingButton>
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
          <DocumentUploader
            caseId={caseId}
            documents={documents}
            onUploaded={(newDocs) => setDocuments((d) => [...d, ...newDocs])}
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
                  hint={documents.length === 0
                    ? "Upload at least one document, then run analysis."
                    : "Click Run analysis to generate an AI Act assessment."}
                  action={
                    <LoadingButton
                      className="primary"
                      loading={running}
                      loadingText="Analyzing…"
                      onClick={handleRunAnalysis}
                      disabled={documents.length === 0}
                    >
                      Run analysis
                    </LoadingButton>
                  }
                />
              )
            )}

            {tab === "chat" && (
              <ChatPanel caseId={caseId} onReassessRequested={handleRunAnalysis} />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
