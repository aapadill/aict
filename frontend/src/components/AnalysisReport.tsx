import React, { useState } from "react";
import type { AnalysisResult, AssessmentSection, Citation, ExtractedFact } from "../types/api";
import EvidencePanel, { CitationItem } from "./EvidencePanel";
import AgentTrace from "./AgentTrace";

function SectionView({ s }: { s: AssessmentSection }) {
  return (
    <div className={`assessment ${s.confidence}`}>
      <div className="head">
        <h3 style={{ margin: 0 }}>{s.title}</h3>
        <span className={`badge ${s.confidence}`}>{s.confidence} confidence</span>
      </div>
      <div className="conclusion">{s.conclusion}</div>
      <div className="reasoning">{s.reasoning}</div>
      {s.assumptions.length > 0 && (
        <div className="sub">
          <strong>Assumptions:</strong>
          <ul>{s.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
      {s.uncertainties.length > 0 && (
        <div className="sub">
          <strong>Uncertainties:</strong>
          <ul>{s.uncertainties.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}
      {s.citations.length > 0 && (
        <div className="sub">
          <strong>Citations:</strong>
          <div style={{ marginTop: 4 }}>
            {s.citations.map((c) => <CitationItem key={c.id} c={c} />)}
          </div>
        </div>
      )}
    </div>
  );
}

function FactView({
  f,
  selectedCitationId,
  onOpenCitation,
}: {
  f: ExtractedFact;
  selectedCitationId?: string;
  onOpenCitation: (citation: Citation) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const primaryCitation = f.citations[0];

  return (
    <div className={`fact ${expanded ? "expanded" : ""}`}>
      <div className="fact-head">
        <div>
          <div className="label">{f.label}</div>
          <div className="fact-count">{f.citations.length} citation{f.citations.length === 1 ? "" : "s"}</div>
        </div>
        <span className={`badge ${f.status}`}>{f.status}</span>
      </div>

      <div className={`value ${expanded ? "" : "fact-summary"}`}>{f.value}</div>

      {primaryCitation ? (
        <button
          className={`citation-chip ${selectedCitationId === primaryCitation.id ? "active" : ""}`}
          onClick={() => onOpenCitation(primaryCitation)}
        >
          <span>{primaryCitation.source_title}</span>
          {primaryCitation.location && <small>{primaryCitation.location}</small>}
        </button>
      ) : (
        <div className="no-citation">No citation attached</div>
      )}

      <div className="fact-actions">
        <button className="ghost compact" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Show less" : "Show more"}
        </button>
        {primaryCitation && (
          <button className="ghost compact" onClick={() => onOpenCitation(primaryCitation)}>
            Open citation
          </button>
        )}
      </div>

      {expanded && f.citations.length > 1 && (
        <div className="fact-more">
          <div className="label">More citations</div>
          {f.citations.slice(1).map((c) => (
            <button
              key={c.id}
              className={`citation-chip secondary ${selectedCitationId === c.id ? "active" : ""}`}
              onClick={() => onOpenCitation(c)}
            >
              <span>{c.source_title}</span>
              {c.location && <small>{c.location}</small>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function CitationPreview({ citation }: { citation: Citation | null }) {
  if (!citation) {
    return (
      <div className="citation-window empty-window">
        <div className="label">Citation window</div>
        <p>Select a cited fact to preview the source context here.</p>
      </div>
    );
  }

  return (
    <div className="citation-window">
      <div className="label">Citation window</div>
      <div className="citation-window-title">{citation.source_title}</div>
      <div className="citation-window-meta">
        <span className="badge">{citation.source_type.replace("_", " ")}</span>
        {citation.location && <span>{citation.location}</span>}
        {citation.verified === false && <span className="badge low">unverified</span>}
      </div>
      <blockquote>{citation.snippet}</blockquote>
    </div>
  );
}

function riskTone(conclusion: string): "high" | "medium" | "low" {
  const text = conclusion.toLowerCase();
  if (text.includes("prohibited") || text.includes("high-risk") || text.includes("high risk")) {
    return "high";
  }
  if (text.includes("limited") || text.includes("transparency") || text.includes("medium")) {
    return "medium";
  }
  return "low";
}

function riskLabel(conclusion: string): string {
  const text = conclusion.toLowerCase();
  if (text.includes("prohibited")) return "Prohibited-risk signal";
  if (text.includes("high-risk") || text.includes("high risk")) return "High AI Act risk";
  if (text.includes("limited")) return "Limited AI Act risk";
  if (text.includes("minimal") || text.includes("low")) return "Low AI Act risk";
  return "Risk needs review";
}

export default function AnalysisReport({
  a,
  onOpenChat,
}: {
  a: AnalysisResult;
  onOpenChat: () => void;
}) {
  const tone = riskTone(a.risk_classification.conclusion);
  const label = riskLabel(a.risk_classification.conclusion);
  const supportedFacts = a.extracted_facts.filter((f) => f.status !== "missing" && f.citations.length > 0);
  const factCitations = supportedFacts.flatMap((f) => f.citations);
  const firstFactCitation = factCitations[0] ?? null;
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const citationPreview =
    selectedCitation && factCitations.some((c) => c.id === selectedCitation.id)
      ? selectedCitation
      : firstFactCitation;

  return (
    <div className="report-stack">
      <section className={`risk-summary-panel ${tone}`}>
        <div>
          <div className="eyebrow">Summary</div>
          <h2>{label}</h2>
          <p>{a.risk_classification.conclusion}</p>
        </div>
        <div className="risk-summary-why">
          <span>Why</span>
          <p>{a.risk_classification.reasoning}</p>
        </div>
        <div className="risk-summary-footer">
          <button className="primary compact" onClick={onOpenChat}>
            Ask about this in the chat
          </button>
          <span className={`badge ${a.risk_classification.confidence}`}>
            {a.risk_classification.confidence} certainty
          </span>
        </div>
      </section>

      <div className="notice">
        <strong>Limitation:</strong> {a.limitation_notice}
      </div>

      <div className="report-overview">
        <section className="panel summary-panel">
          <h2>Use-case summary</h2>
          <p>{a.summary}</p>
        </section>
        <section className="panel report-metrics">
          <div>
            <span>Facts</span>
            <strong>{supportedFacts.length}</strong>
          </div>
          <div>
            <span>Obligations</span>
            <strong>{a.obligations.length}</strong>
          </div>
          <div>
            <span>Missing</span>
            <strong>{a.missing_information.length}</strong>
          </div>
        </section>
      </div>

      <div className="panel facts-panel">
        <div className="section-head">
          <div>
            <h2>Extracted facts</h2>
            <p>Compact facts with cited source context.</p>
          </div>
        </div>
        {supportedFacts.length === 0 ? (
          <div className="muted small">No extracted facts with supporting citations.</div>
        ) : (
          <div className="facts-layout">
            <div className="facts">
              {supportedFacts.map((f) => (
                <FactView
                  key={f.id}
                  f={f}
                  selectedCitationId={citationPreview?.id}
                  onOpenCitation={setSelectedCitation}
                />
              ))}
            </div>
            <CitationPreview citation={citationPreview} />
          </div>
        )}
      </div>

      <div className="panel">
        <h2>AI-system definition assessment</h2>
        <SectionView s={a.ai_system_assessment} />
      </div>

      <div className="panel">
        <h2>Preliminary risk classification</h2>
        <SectionView s={a.risk_classification} />
      </div>

      <div className="panel">
        <h2>Roles & obligations</h2>
        {a.obligations.length === 0 ? (
          <div className="muted small">None identified.</div>
        ) : (
          a.obligations.map((o, i) => <SectionView key={i} s={o} />)
        )}
      </div>

      <div className="panel">
        <h2>Governance observations</h2>
        {a.governance_observations.length === 0 ? (
          <div className="muted small">None.</div>
        ) : (
          a.governance_observations.map((o, i) => <SectionView key={i} s={o} />)
        )}
      </div>

      <div className="panel">
        <h2>Missing information</h2>
        {a.missing_information.length === 0 ? (
          <div className="muted small">None.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {a.missing_information.map((m, i) => <li key={i}>{m}</li>)}
          </ul>
        )}
      </div>

      <div className="panel">
        <div className="section-head">
          <div>
            <h2>Evidence & citations</h2>
            <p>{a.citations.length} cited source{a.citations.length === 1 ? "" : "s"}</p>
          </div>
        </div>
        <EvidencePanel citations={a.citations} />
      </div>

      <div className="panel">
        <div className="section-head">
          <div>
            <h2>Agent trace</h2>
            <p>{a.agent_trace.length} event{a.agent_trace.length === 1 ? "" : "s"}</p>
          </div>
        </div>
        <AgentTrace events={a.agent_trace} />
      </div>

      <div className="panel">
        <h2>Follow-up questions</h2>
        {a.follow_up_questions.length === 0 ? (
          <div className="muted small">None.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {a.follow_up_questions.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        )}
      </div>

      <div className="panel report-chat-cta">
        <div>
          <h2>Continue in chat</h2>
          <p>Ask a follow-up question, challenge the classification, or add new facts for reassessment.</p>
        </div>
        <button className="primary" onClick={onOpenChat}>
          Open chat
        </button>
      </div>
    </div>
  );
}
