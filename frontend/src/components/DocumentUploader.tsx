import React, { useEffect, useRef, useState } from "react";
import { FileText, Trash2, UnlockKeyhole, UploadCloud } from "lucide-react";
import { deleteDocument, uploadDocuments } from "../api/client";
import type { DocumentRecord } from "../types/api";
import LoadingButton from "./LoadingButton";

const ACCEPT = ".pdf,.txt,.md,.markdown,application/pdf,text/plain,text/markdown";

export default function DocumentUploader({
  caseId,
  documents,
  onUploaded,
  onDocumentRemoved,
  onUnlockRequested,
  unlocking = false,
  locked = false,
}: {
  caseId: string;
  documents: DocumentRecord[];
  onUploaded: (docs: DocumentRecord[]) => void;
  onDocumentRemoved?: (documentId: string) => void;
  onUnlockRequested?: () => void | Promise<void>;
  unlocking?: boolean;
  locked?: boolean;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragover, setDragover] = useState(false);
  const [removingDocumentId, setRemovingDocumentId] = useState<string | null>(null);
  const [confirmingDocumentId, setConfirmingDocumentId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (locked) {
      setDragover(false);
    }
  }, [locked]);

  const addFiles = async (files: File[]) => {
    if (locked || uploading) return;
    const allowed = files.filter((f) => /\.(pdf|txt|md|markdown)$/i.test(f.name));
    if (!allowed.length) {
      setError("Only PDF, TXT, or Markdown files are supported.");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setError(
      allowed.length < files.length
        ? "Some files were skipped because only PDF, TXT, or Markdown files are supported."
        : null
    );
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

  const removeUploadedDocument = async (document: DocumentRecord) => {
    if (locked) return;
    setRemovingDocumentId(document.id);
    setError(null);
    try {
      await deleteDocument(caseId, document.id);
      onDocumentRemoved?.(document.id);
      setConfirmingDocumentId(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to remove document");
    } finally {
      setRemovingDocumentId(null);
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
          loading={locked ? unlocking : uploading}
          loadingText={locked ? "Unlocking..." : "Uploading…"}
          onClick={(event) => {
            event.stopPropagation();
            if (locked) {
              onUnlockRequested?.();
              return;
            }
            inputRef.current?.click();
          }}
          className="compact"
          disabled={uploading || unlocking}
        >
          {locked ? <UnlockKeyhole size={14} /> : <UploadCloud size={14} />}
          {locked ? "Locked" : "Add files"}
        </LoadingButton>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          disabled={locked}
          style={{ display: "none" }}
          onChange={(e) => {
            if (e.target.files) void addFiles(Array.from(e.target.files));
          }}
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
          void addFiles(Array.from(e.dataTransfer.files));
        }}
      >
        {locked ? (
          <>Document intake is locked because this case already has an assessment. Unlock to change files.</>
        ) : uploading ? (
          <><span className="spinner" /> Uploading…</>
        ) : (
          <><UploadCloud size={22} /> Drop PDF, TXT, or Markdown files here, or click to choose.</>
        )}
      </div>

      {error && <div className="error-banner" style={{ marginTop: 10 }}>{error}</div>}

      <div className="doc-list" style={{ marginTop: 10 }}>
        {documents.length === 0 ? (
          <div className="muted small" style={{ padding: "6px 0" }}>No documents uploaded yet.</div>
        ) : (
          documents.map((d) => (
            <div key={d.id} className={`doc-row ${locked ? "" : "editable"}`}>
              <span className="file-icon" aria-hidden><FileText size={14} /></span>
              <span className="name">{d.filename}</span>
              <span className={`badge ${d.status}`}>{d.status}</span>
              {!locked && (
                <LoadingButton
                  className="ghost compact icon-only remove-file"
                  loading={false}
                  onClick={(event) => {
                    event.stopPropagation();
                    setConfirmingDocumentId(d.id);
                  }}
                  disabled={removingDocumentId !== null}
                  style={{ minWidth: 30 }}
                  aria-label={`Remove ${d.filename}`}
                  title={`Remove ${d.filename}`}
                >
                  <Trash2 size={14} />
                </LoadingButton>
              )}
              {confirmingDocumentId === d.id && !locked && (
                <div className="doc-confirm" role="dialog" aria-label={`Confirm removal of ${d.filename}`}>
                  <div>
                    <div className="confirm-title">Remove file?</div>
                    <p>This removes it from the case. Saved report snapshots stay in the timeline.</p>
                  </div>
                  <div className="confirm-actions">
                    <button
                      className="ghost compact"
                      onClick={(event) => {
                        event.stopPropagation();
                        setConfirmingDocumentId(null);
                      }}
                      disabled={removingDocumentId === d.id}
                    >
                      Cancel
                    </button>
                    <LoadingButton
                      className="compact confirm-danger"
                      loading={removingDocumentId === d.id}
                      loadingText="Removing..."
                      onClick={(event) => {
                        event.stopPropagation();
                        removeUploadedDocument(d);
                      }}
                    >
                      Delete
                    </LoadingButton>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
