import React, { useEffect, useMemo, useState } from "react";
import { getRuntimeAIStatus, inspectRuntimeArtifact } from "../api/client";
import type { RuntimeAIStatus, RuntimeInspection, RuntimeNode, RuntimeSignal } from "../types/api";
import LoadingButton from "./LoadingButton";

type Point = {
  x: number;
  y: number;
};

export default function RuntimeInspector() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RuntimeInspection | null>(null);
  const [scanStep, setScanStep] = useState(0);
  const [aiStatus, setAIStatus] = useState<RuntimeAIStatus | null>(null);

  const inspect = async (candidate: File | null = file) => {
    if (!candidate) return;
    setFile(candidate);
    setLoading(true);
    setError(null);
    setResult(null);
    setScanStep(0);
    try {
      const data = await inspectRuntimeArtifact(candidate);
      setResult(data);
    } catch (e: any) {
      setError(e?.message ?? "Runtime inspection failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!loading) return;
    const timer = window.setInterval(() => {
      setScanStep((step) => (step + 1) % SCAN_STEPS.length);
    }, 520);
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    getRuntimeAIStatus()
      .then(setAIStatus)
      .catch(() =>
        setAIStatus({
          enabled: false,
          ready: false,
          provider: null,
          model: null,
          message: "AI status check failed.",
        })
      );
  }, []);

  return (
    <div className="runtime-shell">
      <section className="runtime-hero">
        <div>
          <div className="runtime-kicker">Artifact behavior cockpit</div>
          <h1>Drop an artifact. Map the signal field.</h1>
          <AIStatusPill status={aiStatus} />
          <p>
            This pass inspects the uploaded bytes and extracts network, process, path, and format
            signals. It does not execute the artifact on your workstation.
          </p>
          <div className="scan-phases">
            {SCAN_STEPS.map((step, index) => (
              <span key={step} className={loading && index === scanStep ? "active" : result && index < 4 ? "done" : ""}>
                {step}
              </span>
            ))}
          </div>
        </div>
        <div
          className={`runtime-drop ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            inspect(e.dataTransfer.files?.[0] ?? null);
          }}
        >
          <div className="scan-ring" />
          <div className="runtime-drop-title">{file ? file.name : "DROP FILE HERE"}</div>
          <div className="runtime-drop-sub">
            binary, script, archive, text dump, config, anything suspicious
          </div>
          <label className="runtime-picker">
            choose file
            <input
              type="file"
              onChange={(e) => inspect(e.target.files?.[0] ?? null)}
            />
          </label>
          {file && (
            <LoadingButton className="runtime-run" loading={loading} loadingText="Scanning..." onClick={() => inspect()}>
              Re-scan
            </LoadingButton>
          )}
        </div>
      </section>

      {error && <div className="runtime-error">{error}</div>}

      {result ? <InspectionResult result={result} /> : <EmptyConsole loading={loading} scanStep={scanStep} />}
    </div>
  );
}

const SCAN_STEPS = ["fingerprint", "strings", "indicators", "graph", "analysis"];

function AIStatusPill({ status }: { status: RuntimeAIStatus | null }) {
  if (!status) {
    return <div className="ai-health unknown"><span /> AI health: checking</div>;
  }
  const state = status.ready ? "ready" : "off";
  return (
    <div className={`ai-health ${state}`} title={status.message}>
      <span />
      AI health: {status.ready ? "on" : "off"}
      {status.provider && status.model ? <b>{status.provider}:{status.model}</b> : <b>heuristic</b>}
    </div>
  );
}

function EmptyConsole({ loading, scanStep }: { loading: boolean; scanStep: number }) {
  return (
    <div className="runtime-grid">
      <div className="runtime-panel wide">
        <div className="panel-title">Signal graph</div>
        <div className="terminal-empty">
          <span className="cursor-block" /> {loading ? `running ${SCAN_STEPS[scanStep]} module` : "awaiting artifact"}
        </div>
      </div>
      <div className="runtime-panel">
        <div className="panel-title">Analyst feed</div>
        <p className="terminal-line">No telemetry loaded.</p>
        <p className="terminal-line dim">Upload a file to generate the first trace.</p>
      </div>
    </div>
  );
}

function InspectionResult({ result }: { result: RuntimeInspection }) {
  const [selectedId, setSelectedId] = useState("artifact");
  const [filter, setFilter] = useState("all");
  const [visibleEvents, setVisibleEvents] = useState(1);
  const kinds = useMemo(() => ["all", ...Array.from(new Set(result.nodes.filter((node) => node.id !== "artifact").map((node) => node.kind)))], [result.nodes]);
  const selectedNode = result.nodes.find((node) => node.id === selectedId) ?? result.nodes[0];
  const selectedSignal = signalForNode(result, selectedNode);

  useEffect(() => {
    setSelectedId("artifact");
    setFilter("all");
    setVisibleEvents(1);
  }, [result.sha256]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setVisibleEvents((count) => Math.min(result.events.length, count + 1));
    }, 430);
    return () => window.clearInterval(timer);
  }, [result.events.length, result.sha256]);

  return (
    <>
      <div className="runtime-stats">
        <Metric label="Verdict" value={result.verdict.toUpperCase()} tone={result.verdict} />
        <Metric label="Risk" value={`${result.risk_score}/100`} tone={result.verdict} />
        <Metric label="Type" value={result.file_type} />
        <Metric label="Analyst" value={result.analysis_mode} tone={result.analysis_mode === "ai" ? "quiet" : ""} />
        <Metric label="Confidence" value={result.confidence} tone={result.confidence === "low" ? "watch" : "quiet"} />
        <Metric label="Entropy" value={result.entropy.toFixed(2)} />
        <Metric label="Size" value={formatBytes(result.size_bytes)} />
      </div>

      <div className="runtime-grid">
        <div className="runtime-panel wide">
          <div className="runtime-panel-head">
            <div className="panel-title">Signal graph</div>
            <div className="runtime-filters">
              {kinds.map((kind) => (
                <button key={kind} className={filter === kind ? "active" : ""} onClick={() => setFilter(kind)}>
                  {kind}
                </button>
              ))}
            </div>
          </div>
          <SignalGraph result={result} selectedId={selectedNode?.id ?? "artifact"} filter={filter} onSelect={setSelectedId} />
          <NodeInspector node={selectedNode} signal={selectedSignal} result={result} />
        </div>
        <div className="runtime-panel">
          <div className="panel-title">AI analysis</div>
          <div className={`basis-strip ${result.analysis_mode}`}>
            <span>{result.analysis_mode === "ai" ? "AI-assisted" : "heuristic"}</span>
            {result.evaluation_basis}
          </div>
          <p className="runtime-summary">{result.summary}</p>
          <ul className="runtime-analysis">
            {result.analysis.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <div className="hash-box">
            <span>sha256</span>
            <code>{result.sha256}</code>
          </div>
        </div>
        <div className="runtime-panel">
          <div className="panel-title">EU AI Act lens</div>
          <AIActLens result={result} />
        </div>
        <div className="runtime-panel">
          <div className="panel-title">Signal workers</div>
          <SignalWorkers result={result} />
        </div>
        <div className="runtime-panel">
          <div className="panel-title">Timeline</div>
          <div className="timeline">
            {result.events.slice(0, visibleEvents).map((event, index) => (
              <div key={`${event.time}-${event.target}`} className={`runtime-event ${event.severity} ${index === visibleEvents - 1 ? "fresh" : ""}`}>
                <span className="event-time">{event.time}</span>
                <span className="event-body">
                  <b>{event.actor}</b> {event.action} <span>{event.target}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="runtime-panel">
          <div className="panel-title">Extracted signals</div>
          <div className="signal-list">
            {result.signals.length === 0 ? (
              <p className="terminal-line dim">No indicators extracted.</p>
            ) : (
              result.signals.filter((signal) => filter === "all" || signal.kind === filter).map((signal) => (
                <div key={`${signal.kind}-${signal.value}`} className={`signal-row ${signal.severity}`} onClick={() => setSelectedId(nodeIdForSignal(result, signal))}>
                  <span>{signal.kind}</span>
                  <b>{signal.value}</b>
                  <small>{signal.evidence}</small>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}

function SignalWorkers({ result }: { result: RuntimeInspection }) {
  if (result.signal_reviews.length === 0) {
    return <p className="terminal-line dim">No extracted signals reached the worker cap.</p>;
  }
  return (
    <div className="worker-list">
      {result.signal_reviews.map((review) => (
        <div key={`${review.worker}-${review.value}`} className={`worker-card ${review.verdict}`}>
          <div className="worker-card-head">
            <span>{review.worker}</span>
            <b>{review.review_mode}</b>
          </div>
          <div className="worker-signal">
            {review.kind} · {review.value}
          </div>
          <div className="worker-flags">
            <span className={review.verdict}>{review.verdict}</span>
            <span>EU AI Act: {review.eu_ai_act_relevance}</span>
          </div>
          <p>{review.note}</p>
        </div>
      ))}
    </div>
  );
}

function AIActLens({ result }: { result: RuntimeInspection }) {
  const lens = result.ai_act;
  return (
    <div className="ai-act-lens">
      <div className={`ai-act-risk ${lens.risk_hint}`}>
        <span>{lens.relevance}</span>
        <b>{riskHintLabel(lens.risk_hint)}</b>
        <small>confidence: {lens.confidence}</small>
      </div>
      <p>{lens.summary}</p>
      <div className="basis-strip">
        <span>basis</span>
        {lens.basis}
      </div>
      {lens.triggers.length > 0 && (
        <>
          <h3>Signals</h3>
          <ul>
            {lens.triggers.map((trigger) => (
              <li key={trigger}>{trigger}</li>
            ))}
          </ul>
        </>
      )}
      <h3>Questions to verify</h3>
      <ul>
        {lens.follow_up_questions.map((question) => (
          <li key={question}>{question}</li>
        ))}
      </ul>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className={`runtime-metric ${tone ?? ""}`}>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function SignalGraph({
  result,
  selectedId,
  filter,
  onSelect,
}: {
  result: RuntimeInspection;
  selectedId: string;
  filter: string;
  onSelect: (id: string) => void;
}) {
  const positions = useMemo(() => layoutNodes(result.nodes), [result.nodes]);
  const visibleIds = new Set(
    result.nodes
      .filter((node) => node.id === "artifact" || filter === "all" || node.kind === filter)
      .map((node) => node.id)
  );

  return (
    <svg className="signal-graph" viewBox="0 0 900 430" role="img" aria-label="Runtime signal graph">
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3.5" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {result.edges.map((edge) => {
        if (!visibleIds.has(edge.source) || !visibleIds.has(edge.target)) return null;
        const source = positions.get(edge.source);
        const target = positions.get(edge.target);
        if (!source || !target) return null;
        return (
          <g key={`${edge.source}-${edge.target}`}>
            <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} className="graph-edge" />
            <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 4} className="graph-edge-label">
              {edge.label}
            </text>
          </g>
        );
      })}
      {result.nodes.map((node) => {
        if (!visibleIds.has(node.id)) return null;
        const point = positions.get(node.id);
        if (!point) return null;
        return (
          <GraphNode
            key={node.id}
            node={node}
            point={point}
            center={node.id === "artifact"}
            selected={node.id === selectedId}
            onSelect={onSelect}
          />
        );
      })}
    </svg>
  );
}

function GraphNode({
  node,
  point,
  center,
  selected,
  onSelect,
}: {
  node: RuntimeNode;
  point: Point;
  center: boolean;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <g className={`graph-node ${node.severity} ${center ? "center" : ""} ${selected ? "selected" : ""}`} filter="url(#glow)" onClick={() => onSelect(node.id)}>
      <circle cx={point.x} cy={point.y} r={center ? 42 : 27} />
      <text x={point.x} y={point.y + (center ? 4 : 3)} textAnchor="middle">
        {trimMiddle(node.label, center ? 20 : 14)}
      </text>
      {!center && (
        <text x={point.x} y={point.y + 43} textAnchor="middle" className="node-kind">
          {node.kind}
        </text>
      )}
    </g>
  );
}

function NodeInspector({
  node,
  signal,
  result,
}: {
  node?: RuntimeNode;
  signal?: RuntimeSignal;
  result: RuntimeInspection;
}) {
  if (!node) return null;
  return (
    <div className="node-inspector">
      <div>
        <span>selected node</span>
        <b>{node.label}</b>
      </div>
      <div>
        <span>class</span>
        <b>{node.kind}</b>
      </div>
      <div>
        <span>severity</span>
        <b className={node.severity}>{node.severity}</b>
      </div>
      <div className="node-inspector-wide">
        <span>evidence</span>
        <b>{signal?.evidence ?? `artifact fingerprint ${result.sha256.slice(0, 16)}...`}</b>
      </div>
    </div>
  );
}

function signalForNode(result: RuntimeInspection, node?: RuntimeNode): RuntimeSignal | undefined {
  if (!node || node.id === "artifact") return undefined;
  return result.signals.find((signal) => signal.kind === node.kind && node.label.startsWith(signal.value.slice(0, Math.min(signal.value.length, 20))));
}

function nodeIdForSignal(result: RuntimeInspection, signal: RuntimeSignal): string {
  return result.nodes.find((node) => node.kind === signal.kind && signal.value.startsWith(node.label.slice(0, Math.min(node.label.length, 20))))?.id ?? "artifact";
}

function layoutNodes(nodes: RuntimeNode[]): Map<string, Point> {
  const map = new Map<string, Point>();
  map.set("artifact", { x: 450, y: 215 });
  const satellites = nodes.filter((node) => node.id !== "artifact");
  satellites.forEach((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(satellites.length, 1) - Math.PI / 2;
    const radius = index % 2 === 0 ? 158 : 200;
    map.set(node.id, {
      x: 450 + Math.cos(angle) * radius,
      y: 215 + Math.sin(angle) * radius,
    });
  });
  return map;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function riskHintLabel(value: RuntimeInspection["ai_act"]["risk_hint"]): string {
  const labels: Record<RuntimeInspection["ai_act"]["risk_hint"], string> = {
    not_assessable: "Not assessable",
    minimal_or_unclear: "Minimal or unclear",
    limited_risk_possible: "Limited risk possible",
    high_risk_possible: "High-risk possible",
    prohibited_review_needed: "Prohibited review needed",
  };
  return labels[value];
}

function trimMiddle(value: string, max: number): string {
  if (value.length <= max) return value;
  const half = Math.max(3, Math.floor((max - 1) / 2));
  return `${value.slice(0, half)}…${value.slice(-half)}`;
}
