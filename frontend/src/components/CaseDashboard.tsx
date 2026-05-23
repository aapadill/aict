import React, { useEffect, useState } from "react";
import { createCase, deleteCase, listCases } from "../api/client";
import type { Case } from "../types/api";
import EmptyState from "./EmptyState";
import LoadingButton from "./LoadingButton";

export default function CaseDashboard({ onOpen }: { onOpen: (id: string) => void }) {
  const [cases, setCases] = useState<Case[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deletingCaseId, setDeletingCaseId] = useState<string | null>(null);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const data = await listCases();
      setCases(data);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load cases");
      setCases([]);
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
        <div className="section-head">
          <div>
            <h2>Cases board</h2>
            <p>{cases?.length ?? 0} local review{(cases?.length ?? 0) === 1 ? "" : "s"}</p>
          </div>
          <LoadingButton
            className="primary compact"
            loading={creating}
            loadingText="Starting…"
            onClick={startNewCase}
          >
            New case
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
            action={
              <LoadingButton
                className="primary"
                loading={creating}
                loadingText="Starting…"
                onClick={startNewCase}
              >
                New case
              </LoadingButton>
            }
          />
        ) : (
          <div className="case-grid">
            {cases.map((c) => (
              <article key={c.id} className="case-item">
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
                  -
                </button>
                <button className="case-open" onClick={() => onOpen(c.id)}>
                  <div className="title">{c.title}</div>
                  {c.description && <div className="small muted line-clamp">{c.description}</div>}
                  <div className="meta">
                    <span>Updated {new Date(c.updated_at).toLocaleString()}</span>
                    <span>Open</span>
                  </div>
                </button>
                {confirmingDeleteId === c.id && (
                  <div className="case-confirm" role="dialog" aria-label={`Confirm removal of ${c.title}`}>
                    <div className="confirm-title">Remove case?</div>
                    <p>This deletes the local case, report, and uploaded files.</p>
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
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
