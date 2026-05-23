import React from "react";
import type { AgentTraceEvent } from "../types/api";
import EmptyState from "./EmptyState";

export default function AgentTrace({ events }: { events: AgentTraceEvent[] }) {
  if (!events.length) {
    return <EmptyState icon="⌗" title="No trace events yet" hint="Run an analysis to populate the agent trace." />;
  }
  return (
    <div>
      {events.map((e, i) => (
        <div key={i} className="trace-event">
          <div className="row" style={{ gap: 6 }}>
            <span className="agent">{e.agent}</span>
            <span className="action">· {e.action}</span>
          </div>
          <div className="summary">{e.output_summary}</div>
        </div>
      ))}
    </div>
  );
}
