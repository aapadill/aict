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
  const [showForm, setShowForm] = useState(false);

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
      setShowForm(false);
      await load();
      onOpen(c.id);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create case");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="row between" style={{ marginBottom: showForm ? 12 : 0 }}>
          <h2 style={{ margin: 0 }}>Cases</h2>
          <button className="primary" onClick={() => setShowForm((s) => !s)}>
            {showForm ? "Cancel" : "+ New case"}
          </button>
        </div>
        {showForm && (
          <form onSubmit={submit} className="col" style={{ marginTop: 8 }}>
            <div>
              <label>Title</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Recruitment ranking model"
                required
                autoFocus
              />
            </div>
            <div>
              <label>Description (optional)</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description of the AI system or use case."
              />
            </div>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <LoadingButton type="submit" className="primary" loading={creating} loadingText="Creating…">
                Create case
              </LoadingButton>
            </div>
          </form>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <h2>All cases</h2>
        {cases === null ? (
          <div className="muted small"><span className="spinner" /> Loading cases…</div>
        ) : cases.length === 0 ? (
          <EmptyState
            icon="◇"
            title="No cases yet"
            hint="Create your first case to start a compliance review."
            action={
              <button className="primary" onClick={() => setShowForm(true)}>
                + New case
              </button>
            }
          />
        ) : (
          <div className="case-grid">
            {cases.map((c) => (
              <div key={c.id} className="case-item" onClick={() => onOpen(c.id)}>
                <div className="title">{c.title}</div>
                {c.description && <div className="small muted" style={{
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden"
                }}>{c.description}</div>}
                <div className="meta">Updated {new Date(c.updated_at).toLocaleString()}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
