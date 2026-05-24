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
      {c.snippet && <div className="snippet">"{c.snippet}"</div>}
    </div>
  );
}

export default function EvidencePanel({
  citations,
  compact = false,
}: {
  citations: Citation[];
  compact?: boolean;
}) {
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
    <div className={compact ? "evidence-compact" : ""}>
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
