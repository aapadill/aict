import React, { useEffect, useState } from "react";
import { FilePlus2, Trash2 } from "lucide-react";
import { createCase, deleteCase, getAnalysis, listCases } from "../api/client";
import type { AnalysisResult, Case } from "../types/api";
import EmptyState from "./EmptyState";
import LoadingButton from "./LoadingButton";

export default function CaseDashboard({ onOpen }: { onOpen: (id: string) => void }) {
  const [cases, setCases] = useState<Case[] | null>(null);
  const [caseReports, setCaseReports] = useState<Record<string, AnalysisResult | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deletingCaseId, setDeletingCaseId] = useState<string | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const data = await listCases();
      setCases(data);
      const reportPairs = await Promise.all(
        data.map(async (caseRecord) => {
          try {
            return [caseRecord.id, await getAnalysis(caseRecord.id)] as const;
          } catch {
            return [caseRecord.id, null] as const;
          }
        })
      );
      setCaseReports(Object.fromEntries(reportPairs));
    } catch (e: any) {
      setError(e?.message ?? "Failed to load cases");
      setCases([]);
      setCaseReports({});
    }
  };

  useEffect(() => {
    load();
  }, []);

  const startNewCase = async () => {
    setCreating(true);
    setError(null);
    try {
      const c = await createCase({ title: "New AI Act review" });
      await load();
      onOpen(c.id);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create case");
    } finally {
      setCreating(false);
    }
  };

  const reportBadge = (caseId: string) => {
    const report = caseReports[caseId];
    if (report === undefined) return { label: "Checking", tone: "" };
    if (!report) return { label: "Draft", tone: "uploaded" };
    const conclusion = report.risk_classification.conclusion.toLowerCase();
    if (conclusion.includes("prohibited")) return { label: "Prohibited", tone: "low" };
    if (conclusion.includes("high-risk") || conclusion.includes("high risk")) {
      return { label: "High risk", tone: "low" };
    }
    if (conclusion.includes("limited") || conclusion.includes("transparency")) {
      return { label: "Limited risk", tone: "medium" };
    }
    if (conclusion.includes("minimal") || conclusion.includes("low")) {
      return { label: "Low risk", tone: "found" };
    }
    return { label: "Needs review", tone: "uncertain" };
  };

  const removeCase = async (caseRecord: Case) => {
    setDeletingCaseId(caseRecord.id);
    setError(null);
    try {
      await deleteCase(caseRecord.id);
      setCases((current) => current?.filter((item) => item.id !== caseRecord.id) ?? []);
      setConfirmingDeleteId(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to remove case");
    } finally {
      setDeletingCaseId(null);
    }
  };

  return (
    <div className="dashboard-layout">
      <section className="dashboard-main panel">
        <div className="board-header">
          <div>
            <div className="eyebrow">Review workspace</div>
            <h2>Cases board</h2>
            <p>{cases?.length ?? 0} local review{(cases?.length ?? 0) === 1 ? "" : "s"}</p>
          </div>
          <LoadingButton
            className="primary compact"
            loading={creating}
            loadingText="Starting…"
            onClick={startNewCase}
          >
            <FilePlus2 size={15} /> New case
          </LoadingButton>
        </div>

        {error && <div className="error-banner">{error}</div>}
        {cases === null ? (
          <div className="muted small"><span className="spinner" /> Loading cases…</div>
        ) : cases.length === 0 ? (
          <EmptyState
            icon="◇"
            title="No cases yet"
            hint="Create your first case to start a compliance review."
          />
        ) : (
          <div className="case-list">
            {cases.map((c) => {
              const badge = reportBadge(c.id);
              const report = caseReports[c.id];
              return (
                <article key={c.id} className="case-row">
                  <button className="case-open" onClick={() => onOpen(c.id)}>
                    <div className="case-id">{c.id.slice(0, 13)}</div>
                    <div className="case-main">
                      <div className="title">{c.title}</div>
                      <div className="small muted line-clamp">
                        {report?.summary || c.description || "No use-case description saved yet."}
                      </div>
                    </div>
                    <div className="case-meta">
                      <span>Updated {new Date(c.updated_at).toLocaleString()}</span>
                      <span
                        className={`badge ${badge.tone}`}
                        title={report?.risk_classification.conclusion}
                      >
                        {badge.label}
                      </span>
                    </div>
                  </button>
                  <button
                    className="case-delete"
                    onClick={() => {
                      setError(null);
                      setConfirmingDeleteId(c.id);
                    }}
                    disabled={deletingCaseId !== null}
                    aria-label={`Remove ${c.title}`}
                    title={`Remove ${c.title}`}
                  >
                    <Trash2 size={14} />
                  </button>
                  {confirmingDeleteId === c.id && (
                    <div className="case-confirm" role="dialog" aria-label={`Confirm removal of ${c.title}`}>
                      <div>
                        <div className="confirm-title">Remove case?</div>
                        <p>This deletes the local case, report, and uploaded files.</p>
                      </div>
                      <div className="confirm-actions">
                        <button
                          className="ghost compact"
                          onClick={() => setConfirmingDeleteId(null)}
                          disabled={deletingCaseId === c.id}
                        >
                          Cancel
                        </button>
                        <LoadingButton
                          className="compact confirm-danger"
                          loading={deletingCaseId === c.id}
                          loadingText="Deleting..."
                          onClick={() => removeCase(c)}
                        >
                          Delete
                        </LoadingButton>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
