import React from "react";
import type { AnalysisResult, AssessmentSection, Citation, ExtractedFact } from "../types/api";
import { CitationItem } from "./EvidencePanel";

function CitationList({ citations, limit = 2 }: { citations: Citation[]; limit?: number }) {
  const shown = citations.slice(0, limit);
  const remaining = citations.length - shown.length;
  return (
    <div style={{ marginTop: 4 }}>
      {shown.map((c) => <CitationItem key={c.id} c={c} />)}
      {remaining > 0 && (
        <div className="muted small">+{remaining} more citation{remaining === 1 ? "" : "s"} in Evidence.</div>
      )}
    </div>
  );
}

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
          <strong>Evidence:</strong>
          <CitationList citations={s.citations} />
        </div>
      )}
    </div>
  );
}

function FactView({ f }: { f: ExtractedFact }) {
  return (
    <div className="fact">
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div className="label">{f.label}</div>
        <span className={`badge ${f.status}`}>{f.status}</span>
      </div>
      <div className="value">{f.value}</div>
      {f.citations.length > 0 && (
        <div style={{ marginTop: 6 }}>
          <CitationList citations={f.citations} limit={1} />
        </div>
      )}
    </div>
  );
}

export default function AnalysisReport({ a }: { a: AnalysisResult }) {
  return (
    <div>
      <div className="card" style={{ background: "#fff8e1", borderColor: "#e7c97a" }}>
        <strong>⚠ Limitation:</strong> {a.limitation_notice}
      </div>

      <div className="card">
        <h2>Use-case summary</h2>
        <div>{a.summary}</div>
      </div>

      <div className="card">
        <h2>Extracted facts</h2>
        {a.extracted_facts.length === 0 ? (
          <div className="muted small">None extracted.</div>
        ) : (
          <div className="facts">
            {a.extracted_facts.map((f) => <FactView key={f.id} f={f} />)}
          </div>
        )}
      </div>

      <div className="card">
        <h2>AI-system definition assessment</h2>
        <SectionView s={a.ai_system_assessment} />
      </div>

      <div className="card">
        <h2>Preliminary risk classification</h2>
        <SectionView s={a.risk_classification} />
      </div>

      <div className="card">
        <h2>Roles & obligations</h2>
        {a.obligations.length === 0 ? (
          <div className="muted small">None identified.</div>
        ) : (
          a.obligations.map((o, i) => <SectionView key={i} s={o} />)
        )}
      </div>

      <div className="card">
        <h2>Governance observations</h2>
        {a.governance_observations.length === 0 ? (
          <div className="muted small">None.</div>
        ) : (
          a.governance_observations.map((o, i) => <SectionView key={i} s={o} />)
        )}
      </div>

      <div className="card">
        <h2>Missing information</h2>
        {a.missing_information.length === 0 ? (
          <div className="muted small">None.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {a.missing_information.map((m, i) => <li key={i}>{m}</li>)}
          </ul>
        )}
      </div>

      <div className="card">
        <h2>Follow-up questions</h2>
        {a.follow_up_questions.length === 0 ? (
          <div className="muted small">None.</div>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {a.follow_up_questions.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        )}
      </div>
    </div>
  );
}
