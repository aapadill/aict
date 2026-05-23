import type { AnalysisResult, AssessmentSection, Citation } from "../types/api";

type CitationIndex = Map<string, number>;

function citationKey(c: Citation): string {
  return c.chunk_id ?? c.id;
}

function compactText(text: string, maxLength = 220): string {
  const compact = text.replace(/\s+/g, " ").trim();
  if (compact.length <= maxLength) return compact;
  const cutoff = compact.lastIndexOf(" ", maxLength - 3);
  return `${compact.slice(0, cutoff > 80 ? cutoff : maxLength - 3).replace(/[ ,;:]+$/, "")}...`;
}

function allSectionCitations(a: AnalysisResult): Citation[] {
  return [
    ...a.extracted_facts.flatMap((f) => f.citations),
    ...a.ai_system_assessment.citations,
    ...a.risk_classification.citations,
    ...a.obligations.flatMap((o) => o.citations),
    ...a.governance_observations.flatMap((g) => g.citations),
    ...a.citations,
  ];
}

function buildCitationIndex(a: AnalysisResult): CitationIndex {
  const index: CitationIndex = new Map();
  allSectionCitations(a).forEach((citation) => {
    const key = citationKey(citation);
    if (!index.has(key)) {
      index.set(key, index.size + 1);
    }
  });
  return index;
}

function citationRefs(
  citations: Citation[],
  index: CitationIndex,
  limit = 3,
): string {
  const refs = citations
    .map((citation) => index.get(citationKey(citation)))
    .filter((value): value is number => Boolean(value));
  const unique = Array.from(new Set(refs));
  if (!unique.length) return "";

  const shown = unique.slice(0, limit).map((number) => `[${number}]`).join(", ");
  const extra = unique.length > limit ? ` (+${unique.length - limit} more)` : "";
  return `${shown}${extra}`;
}

function citationLine(c: Citation, index: CitationIndex): string {
  const number = index.get(citationKey(c));
  const loc = c.location ? `, ${c.location}` : "";
  return `${number}. _${c.source_type}_ - **${c.source_title}**${loc}: "${compactText(c.snippet)}"`;
}

function cleanList(values: string[]): string[] {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function section(s: AssessmentSection, index: CitationIndex): string {
  const parts = [
    `### ${s.title}`,
    `**Conclusion (${s.confidence} confidence):** ${s.conclusion}`,
    ``,
    `**Why:** ${s.reasoning}`,
  ];

  const refs = citationRefs(s.citations, index);
  if (refs) {
    parts.push(``, `**Evidence:** ${refs}`);
  }

  const assumptions = cleanList(s.assumptions);
  if (assumptions.length) {
    parts.push(``, `**Assumptions:**`, ...assumptions.map((a) => `- ${a}`));
  }

  const uncertainties = cleanList(s.uncertainties);
  if (uncertainties.length) {
    parts.push(``, `**Open questions:**`, ...uncertainties.map((u) => `- ${u}`));
  }

  return parts.join("\n");
}

export function buildMarkdownReport(a: AnalysisResult, caseTitle?: string): string {
  const citationIndex = buildCitationIndex(a);
  const lines: string[] = [];
  lines.push(`# AI Act Assessment - ${caseTitle ?? a.case_id}`);
  lines.push(``);
  lines.push(`> ${a.limitation_notice}`);
  lines.push(``);
  lines.push(`## Use-case summary`);
  lines.push(a.summary);
  lines.push(``);

  lines.push(`## Key facts`);
  if (!a.extracted_facts.length) lines.push(`_None extracted._`);
  a.extracted_facts.forEach((f) => {
    const refs = citationRefs(f.citations, citationIndex, 2);
    const evidence = refs ? ` Evidence: ${refs}.` : "";
    lines.push(`- **${f.label}** (${f.status}): ${f.value || "_Not found._"}${evidence}`);
  });
  lines.push(``);

  lines.push(`## Assessment`);
  lines.push(``);
  lines.push(section(a.ai_system_assessment, citationIndex));
  lines.push(``);
  lines.push(section(a.risk_classification, citationIndex));
  lines.push(``);

  lines.push(`## Obligations`);
  if (!a.obligations.length) lines.push(`_None identified._`);
  a.obligations.forEach((o) => {
    lines.push(section(o, citationIndex));
    lines.push(``);
  });

  lines.push(`## Governance observations`);
  if (!a.governance_observations.length) lines.push(`_None._`);
  a.governance_observations.forEach((g) => {
    lines.push(section(g, citationIndex));
    lines.push(``);
  });

  lines.push(`## Missing information`);
  if (!a.missing_information.length) lines.push(`_None._`);
  cleanList(a.missing_information).forEach((m) => lines.push(`- ${m}`));
  lines.push(``);

  lines.push(`## Follow-up questions`);
  if (!a.follow_up_questions.length) lines.push(`_None._`);
  cleanList(a.follow_up_questions).forEach((q) => lines.push(`- ${q}`));
  lines.push(``);

  lines.push(`## Evidence index`);
  const uniqueCitations = allSectionCitations(a).filter((citation, position, citations) => {
    const key = citationKey(citation);
    return citations.findIndex((candidate) => citationKey(candidate) === key) === position;
  });
  if (!uniqueCitations.length) lines.push(`_None._`);
  uniqueCitations.forEach((c) => lines.push(citationLine(c, citationIndex)));
  lines.push(``);

  lines.push(`## Agent trace`);
  if (!a.agent_trace.length) lines.push(`_None._`);
  a.agent_trace.forEach((e) =>
    lines.push(`- **${e.agent}** - _${e.action}_: ${e.output_summary}`)
  );
  lines.push(``);

  lines.push(`---`);
  lines.push(`> ${a.limitation_notice}`);
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
