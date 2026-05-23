import React from "react";
import type { Citation, SourceType } from "../types/api";
import EmptyState from "./EmptyState";

const GROUPS: { type: SourceType; label: string }[] = [
  { type: "uploaded_document", label: "Uploaded documents" },
  { type: "legislation", label: "Legislation" },
  { type: "official_guidance", label: "Official guidance" },
  { type: "national_guidance", label: "National guidance" },
  { type: "commentary", label: "Commentary" },
  { type: "system", label: "System" },
];

function compactText(text: string, maxLength = 240): string {
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= maxLength) return compact;
  const cutoff = compact.lastIndexOf(" ", maxLength - 3);
  return `${compact.slice(0, cutoff > 80 ? cutoff : maxLength - 3).replace(/[ ,;:]+$/, "")}...`;
}

export function CitationItem({ c }: { c: Citation }) {
  return (
    <div className={`citation ${c.source_type}`}>
      <div className="meta">
        <span className="badge">{c.source_type.replace("_", " ")}</span>
        {c.location && <span style={{ marginLeft: 6 }}>{c.location}</span>}
        {c.verified === false && (
          <span className="badge low" style={{ marginLeft: 6 }}>unverified</span>
        )}
      </div>
      <div className="title">{c.source_title}</div>
      {c.snippet && <div className="snippet">"{compactText(c.snippet)}"</div>}
    </div>
  );
}

export default function EvidencePanel({ citations }: { citations: Citation[] }) {
  if (!citations.length) {
    return (
      <EmptyState
        icon="◧"
        title="No citations yet"
        hint="Run an analysis to populate evidence."
      />
    );
  }
  const grouped = GROUPS.map((g) => ({
    ...g,
    items: citations.filter((c) => c.source_type === g.type),
  })).filter((g) => g.items.length > 0);

  return (
    <div>
      {grouped.map((g) => (
        <div key={g.type} className="cite-group">
          <h3>{g.label} ({g.items.length})</h3>
          {g.items.map((c) => (
            <CitationItem key={c.id} c={c} />
          ))}
        </div>
      ))}
    </div>
  );
}
