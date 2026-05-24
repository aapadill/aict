import type { AnalysisResult, AssessmentSection, Citation } from "../types/api";

function citeLine(c: Citation): string {
  const loc = c.location ? `, ${c.location}` : "";
  return `- _${c.source_type}_ — **${c.source_title}**${loc}: "${c.snippet.trim()}"`;
}

function section(s: AssessmentSection): string {
  const parts = [
    `### ${s.title}`,
    `**Conclusion (${s.confidence} confidence):** ${s.conclusion}`,
    ``,
    `**Reasoning:** ${s.reasoning}`,
  ];
  if (s.assumptions.length) {
    parts.push(``, `**Assumptions:**`, ...s.assumptions.map((a) => `- ${a}`));
  }
  if (s.uncertainties.length) {
    parts.push(``, `**Uncertainties:**`, ...s.uncertainties.map((u) => `- ${u}`));
  }
  if (s.citations.length) {
    parts.push(``, `**Citations:**`, ...s.citations.map(citeLine));
  }
  return parts.join("\n");
}

export function buildMarkdownReport(a: AnalysisResult, caseTitle?: string): string {
  const lines: string[] = [];
  lines.push(`# AI Act Assessment — ${caseTitle ?? a.case_id}`);
  lines.push(``);
  lines.push(`## Use-case summary`);
  lines.push(a.summary);
  lines.push(``);

  lines.push(`## Extracted facts`);
  if (!a.extracted_facts.length) lines.push(`_None extracted._`);
  a.extracted_facts.forEach((f) => {
    lines.push(`- **${f.label}** (${f.status}): ${f.value}`);
    f.citations.forEach((c) => lines.push(`  ${citeLine(c)}`));
  });
  lines.push(``);

  lines.push(`## Assessment`);
  lines.push(``);
  lines.push(section(a.ai_system_assessment));
  lines.push(``);
  lines.push(section(a.risk_classification));
  lines.push(``);

  lines.push(`## Obligations`);
  if (!a.obligations.length) lines.push(`_None identified._`);
  a.obligations.forEach((o) => {
    lines.push(section(o));
    lines.push(``);
  });

  lines.push(`## Governance observations`);
  if (!a.governance_observations.length) lines.push(`_None._`);
  a.governance_observations.forEach((g) => {
    lines.push(section(g));
    lines.push(``);
  });

  lines.push(`## Missing information`);
  if (!a.missing_information.length) lines.push(`_None._`);
  a.missing_information.forEach((m) => lines.push(`- ${m}`));
  lines.push(``);

  lines.push(`## Follow-up questions`);
  if (!a.follow_up_questions.length) lines.push(`_None._`);
  a.follow_up_questions.forEach((q) => lines.push(`- ${q}`));
  lines.push(``);

  lines.push(`## Citations`);
  if (!a.citations.length) lines.push(`_None._`);
  a.citations.forEach((c) => lines.push(citeLine(c)));
  lines.push(``);

  lines.push(`## Agent trace`);
  if (!a.agent_trace.length) lines.push(`_None._`);
  a.agent_trace.forEach((e) =>
    lines.push(`- **${e.agent}** — _${e.action}_: ${e.output_summary}`)
  );
  return lines.join("\n");
}

export function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
