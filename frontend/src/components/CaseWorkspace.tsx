import React, { useEffect, useState } from "react";
import { ArrowLeft, Copy, Download, FileText, MessageSquare, PlayCircle, X } from "lucide-react";
import {
  getAnalysisRevision,
  getAnalysis,
  getCase,
  listAnalysisRevisions,
  listDocuments,
  runAnalysis,
  unlockCaseAnalysis,
  updateCase,
} from "../api/client";
import type { AnalysisResult, AnalysisRevision, Case, DocumentRecord } from "../types/api";
import DocumentUploader from "./DocumentUploader";
import AnalysisReport from "./AnalysisReport";
import ChatPanel from "./ChatPanel";
import EmptyState from "./EmptyState";
import EvidencePanel from "./EvidencePanel";
import AgentTrace from "./AgentTrace";
import LoadingButton from "./LoadingButton";
import { buildMarkdownReport, downloadMarkdown } from "../utils/exportReport";

type Tab = "report" | "chat";

const TAB_LABELS: Record<Tab, string> = {
  report: "Report",
  chat: "Chat",
};

function revisionTone(revision: AnalysisRevision): string {
  const label = revision.risk_label.toLowerCase();
  if (label.includes("high") || label.includes("prohibited")) return "low";
  if (label.includes("limited")) return "medium";
  if (label.includes("low")) return "found";
  return "uncertain";
}

function StatusDropdown({
  title,
  value,
  defaultOpen = false,
  children,
}: {
  title: string;
  value: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <details
      className="status-dropdown"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="status-summary">
        <span>{title}</span>
        <strong>{value}</strong>
      </summary>
      <div className="status-content">{children}</div>
    </details>
  );
}

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
  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisResult | null>(null);
  const [analysisHistory, setAnalysisHistory] = useState<AnalysisRevision[]>([]);
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(null);
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
  const [confirmingUnlock, setConfirmingUnlock] = useState(false);
  const [unlocking, setUnlocking] = useState(false);

  const loadHistory = async () => {
    try {
      const revisions = await listAnalysisRevisions(caseId);
      setAnalysisHistory(revisions);
      return revisions;
    } catch {
      setAnalysisHistory([]);
      return [];
    }
  };

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
      const revisions = await loadHistory();
      const activeRevision = revisions.find((revision) => revision.active);
      setActiveAnalysis(a);
      setAnalysis(a);
      setSelectedRevisionId(activeRevision?.id ?? null);
    } catch (e: any) {
      const revisions = await loadHistory();
      // 404 likely means no analysis yet — keep null
      if (!/404/.test(String(e?.message))) {
        setError((prev) => prev ?? (e?.message ?? "Failed to load analysis"));
      }
      setActiveAnalysis(null);
      setAnalysis(null);
      setSelectedRevisionId(null);
      if (revisions.some((revision) => revision.active)) {
        setAnalysisHistory(revisions.map((revision) => ({ ...revision, active: false })));
      }
    } finally {
      setLoadingAnalysis(false);
    }
  };

  useEffect(() => {
    loadAll();
     
  }, [caseId]);

  useEffect(() => {
    if (!activeAnalysis && tab === "chat") {
      setTab("report");
    }
  }, [activeAnalysis, tab]);

  useEffect(() => {
    if (!confirmingUnlock) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !unlocking) {
        setConfirmingUnlock(false);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [confirmingUnlock, unlocking]);

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
      const revisions = await loadHistory();
      const activeRevision = revisions.find((revision) => revision.active);
      setActiveAnalysis(a);
      setAnalysis(a);
      setSelectedRevisionId(activeRevision?.id ?? null);
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
    if (activeAnalysis) return;
    setDocuments((current) => {
      const existing = new Set(current.map((doc) => doc.id));
      return [
        ...current,
        ...newDocs.filter((doc) => !existing.has(doc.id)),
      ];
    });
    setAnalysis(null);
    setSelectedRevisionId(null);
  };

  const handleDocumentRemoved = (documentId: string) => {
    setDocuments((current) => current.filter((document) => document.id !== documentId));
    setAnalysis(null);
    setSelectedRevisionId(null);
  };

  const handleUnlockAnalysis = async () => {
    setUnlocking(true);
    setError(null);
    try {
      await unlockCaseAnalysis(caseId);
      const docs = await listDocuments(caseId);
      await loadHistory();
      setDocuments(docs);
      setActiveAnalysis(null);
      setAnalysis(null);
      setSelectedRevisionId(null);
      setConfirmingUnlock(false);
      setTab("report");
    } catch (e: any) {
      setError(e?.message ?? "Failed to unlock case");
    } finally {
      setUnlocking(false);
    }
  };

  const handleReassessFromChat = async () => {
    await handleRunAnalysis();
    setTab("report");
  };

  const handleSelectRevision = async (revision: AnalysisRevision) => {
    setLoadingAnalysis(true);
    setError(null);
    try {
      const selected = await getAnalysisRevision(caseId, revision.id);
      setAnalysis(selected);
      setSelectedRevisionId(revision.id);
      setTab("report");
    } catch (e: any) {
      setError(e?.message ?? "Failed to load report revision");
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const handleShowWorkingDraft = () => {
    setAnalysis(activeAnalysis);
    setSelectedRevisionId(analysisHistory.find((revision) => revision.active)?.id ?? null);
    setTab("report");
  };

  const intakeLocked = Boolean(activeAnalysis);
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
  const headerDescription = activeAnalysis ? caseData?.description : null;
  const activeRevision = analysisHistory.find((revision) => revision.active);
  const selectedRevision = analysisHistory.find((revision) => revision.id === selectedRevisionId);
  const viewingHistoricalRevision = Boolean(
    selectedRevision && (!activeRevision || selectedRevision.id !== activeRevision.id),
  );

  const tabItems: { id: Tab; label: string; meta: string }[] = [
    {
      id: "report",
      label: TAB_LABELS.report,
      meta: analysis ? (viewingHistoricalRevision ? "History" : "Ready") : "Draft",
    },
    { id: "chat", label: TAB_LABELS.chat, meta: activeAnalysis ? "Ask" : "Locked" },
  ];

  if (loadingCase && !caseData) {
    return <div className="card"><span className="spinner" /> Loading case…</div>;
  }
  if (!caseData) {
    return (
      <div className="card">
        <div className="error-banner">{error ?? "Case not found"}</div>
        <button onClick={onBack}><ArrowLeft size={14} /> Back to cases</button>
      </div>
    );
  }

  return (
    <div className="workspace-page">
      <div className="workspace-hero">
        <button className="ghost back-button" onClick={onBack}><ArrowLeft size={14} /> Cases</button>
        <div className="workspace-head">
          <div className="title-block">
            <div className="eyebrow">Compliance review</div>
            <h1>{caseData.title}</h1>
            {headerDescription && <p>{headerDescription}</p>}
            <div className="workspace-meta">
              <span>Created {new Date(caseData.created_at).toLocaleString()}</span>
              <span>{documents.length} document{documents.length === 1 ? "" : "s"}</span>
              <span className={`badge ${activeAnalysis ? "parsed" : ""}`}>
                {activeAnalysis ? "analysis ready" : "editable draft"}
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
              <Copy size={14} /> {copied ? "Copied" : "Copy Markdown"}
            </LoadingButton>
            <LoadingButton
              loading={exporting}
              loadingText="Exporting…"
              onClick={handleDownload}
              disabled={!analysis}
            >
              <Download size={14} /> Download .md
            </LoadingButton>
          </div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {confirmingUnlock && (
        <div
          className="modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !unlocking) {
              setConfirmingUnlock(false);
            }
          }}
        >
          <div
            className="modal-card unlock-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="unlock-title"
          >
            <button
              className="modal-close"
              type="button"
              onClick={() => setConfirmingUnlock(false)}
              disabled={unlocking}
              aria-label="Cancel unlock"
              title="Cancel unlock"
            >
              <X size={16} />
            </button>
            <div className="modal-body">
              <div className="eyebrow">Locked report</div>
              <h2 id="unlock-title">Unlock this case?</h2>
              <p>
                Unlocking lets you edit the case files again.
              </p>
              <p>
                The current generated report will stay in the timeline. Active chat history will
                reset, and you can add or remove files before running a fresh analysis.
              </p>
            </div>
            <div className="modal-actions">
              <button
                className="ghost compact"
                onClick={() => setConfirmingUnlock(false)}
                disabled={unlocking}
              >
                Cancel
              </button>
              <LoadingButton
                className="compact confirm-danger"
                loading={unlocking}
                loadingText="Unlocking..."
                onClick={handleUnlockAnalysis}
              >
                Proceed
              </LoadingButton>
            </div>
          </div>
        </div>
      )}

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
            onDocumentRemoved={handleDocumentRemoved}
            onUnlockRequested={() => setConfirmingUnlock(true)}
            unlocking={unlocking}
            locked={intakeLocked}
          />
          <div className="panel case-summary">
            <h2>Case status</h2>
            <StatusDropdown title="Report timeline" value={analysisHistory.length} defaultOpen>
              {analysisHistory.length === 0 ? (
                <div className="muted small">No reports have been generated yet.</div>
              ) : (
                <div className="revision-timeline">
                  {!activeAnalysis && (
                    <button
                      className={`revision-item draft ${selectedRevisionId === null ? "selected" : ""}`}
                      onClick={handleShowWorkingDraft}
                    >
                      <span className="revision-dot" />
                      <span className="revision-body">
                        <strong>Working draft</strong>
                        <small>Edit files, then run a fresh analysis.</small>
                      </span>
                    </button>
                  )}
                  {analysisHistory.map((revision) => (
                    <button
                      key={revision.id}
                      className={`revision-item ${selectedRevisionId === revision.id ? "selected" : ""}`}
                      onClick={() => handleSelectRevision(revision)}
                    >
                      <span className={`revision-dot ${revision.active ? "active" : ""}`} />
                      <span className="revision-body">
                        <strong>
                          Report v{revision.revision}
                          {revision.active ? " · active" : ""}
                        </strong>
                        <small>{new Date(revision.created_at).toLocaleString()}</small>
                        <span className={`badge ${revisionTone(revision)}`}>
                          {revision.risk_label}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </StatusDropdown>
            {analysis ? (
              <>
                <StatusDropdown
                  title="Missing information"
                  value={analysis.missing_information.length}
                >
                  {analysis.missing_information.length === 0 ? (
                    <div className="muted small">None.</div>
                  ) : (
                    <ul className="status-list">
                      {analysis.missing_information.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  )}
                </StatusDropdown>

                <StatusDropdown title="Citations" value={analysis.citations.length}>
                  <EvidencePanel citations={analysis.citations} compact />
                </StatusDropdown>

                <StatusDropdown
                  title="Follow-up questions"
                  value={analysis.follow_up_questions.length}
                >
                  {analysis.follow_up_questions.length === 0 ? (
                    <div className="muted small">None.</div>
                  ) : (
                    <ul className="status-list">
                      {analysis.follow_up_questions.map((question, index) => (
                        <li key={index}>{question}</li>
                      ))}
                    </ul>
                  )}
                </StatusDropdown>

                <StatusDropdown title="Agent trace" value={analysis.agent_trace.length}>
                  <AgentTrace events={analysis.agent_trace} />
                </StatusDropdown>
              </>
            ) : (
              <div className="muted small">
                Run analysis to populate missing facts, citations, questions, and trace events.
              </div>
            )}
          </div>
        </aside>

        <section className="workspace-main">
          <div className="tabs" role="tablist" aria-label="Case workspace">
            {tabItems.map((item) => (
              <button
                key={item.id}
                role="tab"
                aria-selected={tab === item.id}
                disabled={item.id === "chat" && !activeAnalysis}
                className={tab === item.id ? "active" : ""}
                onClick={() => setTab(item.id)}
              >
                <span>
                  {item.id === "report" ? <FileText size={15} /> : <MessageSquare size={15} />}
                  {item.label}
                </span>
                <small>{item.meta}</small>
              </button>
            ))}
          </div>

          <div className="tab-panel" role="tabpanel" aria-label={TAB_LABELS[tab]}>
            {tab === "report" && (
              loadingAnalysis ? (
                <div className="panel"><span className="spinner" /> Loading analysis…</div>
              ) : analysis ? (
                <>
                  {viewingHistoricalRevision && selectedRevision && (
                    <div className="notice history-notice">
                      Viewing Report v{selectedRevision.revision} from{" "}
                      {new Date(selectedRevision.created_at).toLocaleString()}. This is a saved
                      snapshot; run a fresh analysis to create a new report.
                    </div>
                  )}
                  <AnalysisReport
                    a={analysis}
                    onOpenChat={() => {
                      if (activeAnalysis) setTab("chat");
                    }}
                    readOnly={viewingHistoricalRevision || !activeAnalysis}
                  />
                </>
              ) : (
                <EmptyState
                  icon="◷"
                  title={analysisHistory.length ? "No active report" : "No analysis yet"}
                  hint={analysisHistory.length
                    ? "Select a saved report from the timeline, or run a fresh analysis for the current files."
                    : !descriptionReady
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
                      <PlayCircle size={16} /> Run analysis
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
