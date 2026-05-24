import React, { useEffect, useRef, useState } from "react";
import { MessageSquare, Send, RefreshCw } from "lucide-react";
import { getMessages, sendChatMessage } from "../api/client";
import type { ChatMessage, ChatResponse } from "../types/api";
import EmptyState from "./EmptyState";
import LoadingButton from "./LoadingButton";
import { CitationItem } from "./EvidencePanel";

export default function ChatPanel({
  caseId,
  onReassessRequested,
  reassessing = false,
}: {
  caseId: string;
  onReassessRequested: () => void | Promise<void>;
  reassessing?: boolean;
}) {
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<ChatResponse | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const load = async () => {
    setError(null);
    try {
      const data = await getMessages(caseId);
      setMessages(data);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load messages");
      setMessages([]);
    }
  };

  useEffect(() => {
    load();
     
  }, [caseId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || sending) return;
    const text = input.trim();
    setInput("");
    setSending(true);
    setError(null);
    // optimistic
    setMessages((m) => [
      ...(m ?? []),
      {
        id: `tmp-${Date.now()}`,
        case_id: caseId,
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
      },
    ]);
    try {
      const resp = await sendChatMessage(caseId, text);
      setLastResponse(resp);
      await load();
    } catch (e: any) {
      setError(e?.message ?? "Failed to send message");
    } finally {
      setSending(false);
    }
  };

  const runReassessment = async () => {
    setError(null);
    try {
      await onReassessRequested();
      setLastResponse(null);
    } catch (e: any) {
      setError(e?.message ?? "Reanalysis failed");
    }
  };

  const canSend = Boolean(input.trim()) && !sending;

  return (
    <div className="panel chat-panel">
      <div className="section-head">
        <div>
          <h2><MessageSquare size={15} /> Follow-up chat</h2>
          <p>{messages?.length ?? 0} message{(messages?.length ?? 0) === 1 ? "" : "s"}</p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {messages === null ? (
        <div className="muted small"><span className="spinner" /> Loading…</div>
      ) : messages.length === 0 ? (
        <EmptyState icon="✎" title="No messages yet" hint="Ask a follow-up question about the assessment." />
      ) : (
        <div className="chat">
          {messages.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              <div className="role">{m.role}</div>
              <div className="content">{m.content}</div>
              {m.citations && m.citations.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  {m.citations.map((c) => <CitationItem key={c.id} c={c} />)}
                </div>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>
      )}

      {lastResponse && (lastResponse.new_facts_detected.length > 0 || lastResponse.reassessment_recommended) && (
        <div className="notice action-notice">
          {lastResponse.new_facts_detected.length > 0 && (
            <div className="small">
              <strong>New facts detected:</strong>
              <ul style={{ margin: "4px 0 0 18px" }}>
                {lastResponse.new_facts_detected.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          )}
          {lastResponse.reassessment_recommended && (
            <div className="row between" style={{ marginTop: 8 }}>
              <span className="small"><strong>Reassessment recommended</strong> based on the latest exchange.</span>
              <LoadingButton
                className="primary"
                loading={reassessing}
                loadingText="Analyzing…"
                onClick={runReassessment}
              >
                <RefreshCw size={14} /> Update report
              </LoadingButton>
            </div>
          )}
        </div>
      )}

      <div className="chat-input">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a follow-up question…"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              send();
            }
          }}
        />
        <LoadingButton
          className="primary"
          loading={sending}
          loadingText="Sending…"
          onClick={send}
          disabled={!canSend}
        >
          <Send size={14} /> Send
        </LoadingButton>
      </div>
      <div className="small muted" style={{ marginTop: 4 }}>Tip: ⌘/Ctrl+Enter to send.</div>
    </div>
  );
}
