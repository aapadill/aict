import React, { useRef, useState } from "react";
import { uploadDocuments } from "../api/client";
import type { DocumentRecord } from "../types/api";
import LoadingButton from "./LoadingButton";

const ACCEPT = ".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown";

export default function DocumentUploader({
  caseId,
  documents,
  onUploaded,
}: {
  caseId: string;
  documents: DocumentRecord[];
  onUploaded: (docs: DocumentRecord[]) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragover, setDragover] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: File[]) => {
    const allowed = files.filter((f) => /\.(pdf|txt|md|markdown)$/i.test(f.name));
    if (!allowed.length) {
      setError("Only PDF, TXT, or Markdown files are supported.");
      return;
    }
    setError(null);
    setUploading(true);
    try {
      const created = await uploadDocuments(caseId, allowed);
      onUploaded(created);
    } catch (e: any) {
      setError(e?.message ?? "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="panel document-panel">
      <div className="section-head compact-head">
        <div>
          <h2>Documents</h2>
          <p>{documents.length} file{documents.length === 1 ? "" : "s"} in this case</p>
        </div>
        <LoadingButton
          loading={uploading}
          loadingText="Uploading…"
          onClick={() => inputRef.current?.click()}
          className="compact"
        >
          Upload
        </LoadingButton>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          style={{ display: "none" }}
          onChange={(e) => e.target.files && handleFiles(Array.from(e.target.files))}
        />
      </div>

      <div
        className={`dropzone ${dragover ? "dragover" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragover(true);
        }}
        onDragLeave={() => setDragover(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragover(false);
          handleFiles(Array.from(e.dataTransfer.files));
        }}
      >
        {uploading ? (
          <><span className="spinner" /> Uploading…</>
        ) : (
          <>Drop PDF, TXT, or Markdown files here, or click to browse.</>
        )}
      </div>

      {error && <div className="error-banner" style={{ marginTop: 10 }}>{error}</div>}

      <div className="doc-list" style={{ marginTop: 10 }}>
        {documents.length === 0 ? (
          <div className="muted small" style={{ padding: "6px 0" }}>No documents uploaded yet.</div>
        ) : (
          documents.map((d) => (
            <div key={d.id} className="doc-row">
              <span className="file-icon" aria-hidden>DOC</span>
              <span className="name">{d.filename}</span>
              <span className={`badge ${d.status}`}>{d.status}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
