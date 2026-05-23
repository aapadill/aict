import React, { useEffect, useRef, useState } from "react";
import { uploadDocuments } from "../api/client";
import type { DocumentRecord } from "../types/api";
import LoadingButton from "./LoadingButton";

const ACCEPT = ".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown";
const fileKey = (file: File) => `${file.name}:${file.size}:${file.lastModified}`;

export default function DocumentUploader({
  caseId,
  documents,
  onUploaded,
  locked = false,
}: {
  caseId: string;
  documents: DocumentRecord[];
  onUploaded: (docs: DocumentRecord[]) => void;
  locked?: boolean;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragover, setDragover] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (locked) {
      setPendingFiles([]);
      setDragover(false);
    }
  }, [locked]);

  const addFiles = (files: File[]) => {
    if (locked) return;
    const allowed = files.filter((f) => /\.(pdf|txt|md|markdown)$/i.test(f.name));
    if (!allowed.length) {
      setError("Only PDF, TXT, or Markdown files are supported.");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setPendingFiles((current) => {
      const existing = new Set(current.map(fileKey));
      const next = allowed.filter((file) => !existing.has(fileKey(file)));
      return [...current, ...next];
    });
    setError(
      allowed.length < files.length
        ? "Some files were skipped because only PDF, TXT, or Markdown files are supported."
        : null
    );
    if (inputRef.current) inputRef.current.value = "";
  };

  const removePendingFile = (key: string) => {
    setPendingFiles((files) => files.filter((file) => fileKey(file) !== key));
  };

  const uploadPendingFiles = async () => {
    if (locked) return;
    if (!pendingFiles.length) {
      inputRef.current?.click();
      return;
    }
    setError(null);
    setUploading(true);
    try {
      const created = await uploadDocuments(caseId, pendingFiles);
      onUploaded(created);
      setPendingFiles([]);
    } catch (e: any) {
      setError(e?.message ?? "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="panel document-panel">
      <div className="section-head compact-head">
        <div>
          <h2>Documents</h2>
          <p>
            {locked
              ? "Files are locked after analysis."
              : `${documents.length} file${documents.length === 1 ? "" : "s"} in this case`}
          </p>
        </div>
        <LoadingButton
          loading={uploading}
          loadingText="Uploading…"
          onClick={(event) => {
            event.stopPropagation();
            if (locked) return;
            inputRef.current?.click();
          }}
          className="compact"
          disabled={locked}
        >
          {locked ? "Locked" : "Add files"}
        </LoadingButton>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          disabled={locked}
          style={{ display: "none" }}
          onChange={(e) => e.target.files && addFiles(Array.from(e.target.files))}
        />
      </div>

      <div
        className={`dropzone ${dragover ? "dragover" : ""} ${locked ? "locked" : ""}`}
        onClick={() => !locked && !uploading && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (locked) return;
          setDragover(true);
        }}
        onDragLeave={() => setDragover(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragover(false);
          if (locked) return;
          addFiles(Array.from(e.dataTransfer.files));
        }}
      >
        {locked ? (
          <>Document intake is locked because this case already has an assessment.</>
        ) : uploading ? (
          <><span className="spinner" /> Uploading…</>
        ) : (
          <>Drop PDF, TXT, or Markdown files here, or click to choose.</>
        )}
      </div>

      {error && <div className="error-banner" style={{ marginTop: 10 }}>{error}</div>}

      {pendingFiles.length > 0 && (
        <div className="pending-files">
          <div className="row between">
            <div>
              <h3>Selected for upload</h3>
              <p>{pendingFiles.length} file{pendingFiles.length === 1 ? "" : "s"} ready</p>
            </div>
            <LoadingButton
              className="primary compact"
              loading={uploading}
              loadingText="Uploading…"
              onClick={(event) => {
                event.stopPropagation();
                uploadPendingFiles();
              }}
              disabled={locked}
            >
              Upload selected
            </LoadingButton>
          </div>
          <div className="pending-list">
            {pendingFiles.map((file) => (
              <div key={fileKey(file)} className="pending-row">
                <span className="file-icon" aria-hidden>DOC</span>
                <span className="name">{file.name}</span>
                <button
                  className="ghost compact remove-file"
                  onClick={(event) => {
                    event.stopPropagation();
                    removePendingFile(fileKey(file));
                  }}
                  disabled={uploading}
                  title={`Remove ${file.name}`}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

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
