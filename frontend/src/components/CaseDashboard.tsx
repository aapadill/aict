import React, { useEffect, useState } from "react";
import { createCase, listCases } from "../api/client";
import type { Case } from "../types/api";
import EmptyState from "./EmptyState";
import LoadingButton from "./LoadingButton";

export default function CaseDashboard({ onOpen }: { onOpen: (id: string) => void }) {
  const [cases, setCases] = useState<Case[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

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

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const c = await createCase({ title: title.trim(), description: description.trim() || undefined });
      setTitle("");
      setDescription("");
      await load();
      onOpen(c.id);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create case");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="dashboard-layout">
      <section className="dashboard-main panel">
        <div className="section-head">
          <div>
            <h2>Cases</h2>
            <p>{cases?.length ?? 0} local review{(cases?.length ?? 0) === 1 ? "" : "s"}</p>
          </div>
          <button className="primary compact" onClick={() => document.getElementById("case-title")?.focus()}>
            New case
          </button>
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
              <button className="primary" onClick={() => document.getElementById("case-title")?.focus()}>
                New case
              </button>
            }
          />
        ) : (
          <div className="case-grid">
            {cases.map((c) => (
              <button key={c.id} className="case-item" onClick={() => onOpen(c.id)}>
                <div className="title">{c.title}</div>
                {c.description && <div className="small muted line-clamp">{c.description}</div>}
                <div className="meta">
                  <span>Updated {new Date(c.updated_at).toLocaleString()}</span>
                  <span>Open</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <aside className="dashboard-side panel">
        <h2>New case</h2>
        <form onSubmit={submit} className="form-stack">
          <div>
            <label htmlFor="case-title">Title</label>
            <input
              id="case-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Recruitment ranking model"
              required
            />
          </div>
          <div>
            <label htmlFor="case-description">Description</label>
            <textarea
              id="case-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of the AI system or use case."
            />
          </div>
          <LoadingButton type="submit" className="primary full" loading={creating} loadingText="Creating…">
            Create case
          </LoadingButton>
        </form>
      </aside>
    </div>
  );
}
