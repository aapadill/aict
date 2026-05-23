import React, { useEffect, useState } from "react";
import {
  ApiError,
  getAnalysis,
  getCase,
  listDocuments,
  runAnalysis,
} from "../api/client";
import type { AnalysisResult, Case, DocumentRecord } from "../types/api";
import DocumentUploader from "./DocumentUploader";
import AnalysisReport from "./AnalysisReport";
import EvidencePanel from "./EvidencePanel";
import ChatPanel from "./ChatPanel";
import AgentTrace from "./AgentTrace";
import EmptyState from "./EmptyState";
import LoadingButton from "./LoadingButton";
import { buildMarkdownReport, downloadMarkdown } from "../utils/exportReport";

type Tab = "report" | "evidence" | "chat" | "trace";

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
  const [llmError, setLlmError] = useState(false);
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
    setLlmError(false);
    try {
      const a = await runAnalysis(caseId);
      setAnalysis(a);
      setTab("report");
    } catch (e: any) {
      if (e instanceof ApiError && e.code === "llm_not_configured") {
        setLlmError(true);
      } else {
        setError(e?.message ?? "Analysis failed");
      }
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
    <div>
      <div className="row" style={{ marginBottom: 10 }}>
        <button className="ghost" onClick={onBack}>← Cases</button>
      </div>

      <div className="card">
        <div className="workspace-head">
          <div className="title-block" style={{ minWidth: 0, flex: 1 }}>
            <h1 style={{ wordBreak: "break-word" }}>{caseData.title}</h1>
            {caseData.description && <p style={{ wordBreak: "break-word" }}>{caseData.description}</p>}
            <div className="small faint" style={{ marginTop: 4 }}>
              Created {new Date(caseData.created_at).toLocaleString()} · {documents.length} document(s) ·{" "}
              Analysis: {analysis ? <span className="badge parsed">ready</span> : <span className="badge">none</span>}
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
              ▶ Run analysis
            </LoadingButton>
            <LoadingButton
              loading={copying}
              loadingText="Copying…"
              onClick={handleCopy}
              disabled={!analysis}
            >
              {copied ? "✓ Copied" : "⧉ Copy Markdown"}
            </LoadingButton>
            <LoadingButton
              loading={exporting}
              loadingText="Exporting…"
              onClick={handleDownload}
              disabled={!analysis}
            >
              ⬇ Download .md
            </LoadingButton>
          </div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {llmError && (
        <div className="llm-setup-banner">
          <strong>⚠ LLM not configured — analysis cannot run.</strong>
          <span>
            {" "}Add per-agent model variables to your <code>.env</code> file and restart the backend.
            See <code>.env.example</code> for provider options (vllm, anthropic, openai).
          </span>
          <details style={{ marginTop: 6 }}>
            <summary style={{ cursor: "pointer" }}>Show required variables</summary>
            <pre>{[
              "VLLM_BASE_URL=http://your-server:8000/v1",
              "VLLM_API_KEY=your-key",
              "DOCUMENT_FACT_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "AI_SYSTEM_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "RISK_CLASSIFICATION_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "OBLIGATIONS_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "CRITIC_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
              "CHAT_AGENT_MODEL=vllm:meta-llama/Llama-3.3-70B-Instruct",
            ].join("\n")}</pre>
          </details>
        </div>
      )}

      <DocumentUploader
        caseId={caseId}
        documents={documents}
        onUploaded={(newDocs) => setDocuments((d) => [...d, ...newDocs])}
      />

      <div className="tabs">
        <button className={tab === "report" ? "active" : ""} onClick={() => setTab("report")}>Report</button>
        <button className={tab === "evidence" ? "active" : ""} onClick={() => setTab("evidence")}>Evidence</button>
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>Chat</button>
        <button className={tab === "trace" ? "active" : ""} onClick={() => setTab("trace")}>Agent trace</button>
      </div>

      {tab === "report" && (
        loadingAnalysis ? (
          <div className="card"><span className="spinner" /> Loading analysis…</div>
        ) : analysis ? (
          <AnalysisReport a={analysis} />
        ) : (
          <EmptyState
            icon="◷"
            title="No analysis yet"
            hint={documents.length === 0
              ? "Upload at least one document, then run analysis."
              : "Click 'Run analysis' to generate an AI Act assessment."}
            action={
              <LoadingButton
                className="primary"
                loading={running}
                loadingText="Analyzing…"
                onClick={handleRunAnalysis}
                disabled={documents.length === 0}
              >
                ▶ Run analysis
              </LoadingButton>
            }
          />
        )
      )}

      {tab === "evidence" && (
        <div className="card">
          <h2>Evidence & citations</h2>
          <EvidencePanel citations={analysis?.citations ?? []} />
        </div>
      )}

      {tab === "chat" && (
        <ChatPanel caseId={caseId} onReassessRequested={handleRunAnalysis} />
      )}

      {tab === "trace" && (
        <div className="card">
          <h2>Agent trace</h2>
          <AgentTrace events={analysis?.agent_trace ?? []} />
        </div>
      )}
    </div>
  );
}
