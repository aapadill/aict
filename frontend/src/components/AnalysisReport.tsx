import React from "react";
import type { AnalysisResult, AssessmentSection, ExtractedFact } from "../types/api";
import { CitationItem } from "./EvidencePanel";

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
          {f.citations.map((c) => <CitationItem key={c.id} c={c} />)}
        </div>
      )}
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

export default function AnalysisReport({ a }: { a: AnalysisResult }) {
  const tone = riskTone(a.risk_classification.conclusion);
  const label = riskLabel(a.risk_classification.conclusion);

  return (
    <div className="report-stack">
      <section className={`tldr-panel ${tone}`}>
        <div>
          <div className="eyebrow">TL;DR</div>
          <h2>{label}</h2>
          <p>{a.risk_classification.conclusion}</p>
        </div>
        <div className="tldr-why">
          <span>Why</span>
          <p>{a.risk_classification.reasoning}</p>
          <span className={`badge ${a.risk_classification.confidence}`}>
            {a.risk_classification.confidence} confidence
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
            <strong>{a.extracted_facts.length}</strong>
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

      <div className="panel">
        <h2>Extracted facts</h2>
        {a.extracted_facts.length === 0 ? (
          <div className="muted small">None extracted.</div>
        ) : (
          <div className="facts">
            {a.extracted_facts.map((f) => <FactView key={f.id} f={f} />)}
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
