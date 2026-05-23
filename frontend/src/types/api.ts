export type SourceType =
  | "uploaded_document"
  | "legislation"
  | "official_guidance"
  | "national_guidance"
  | "commentary"
  | "system";

export type Case = {
  id: string;
  title: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentRecord = {
  id: string;
  case_id: string;
  filename: string;
  content_type?: string | null;
  status: "uploaded" | "parsed" | "empty" | "unreadable" | "failed";
  created_at: string;
};

export type Citation = {
  id: string;
  source_id?: string;
  chunk_id?: string;
  source_type: SourceType;
  source_title: string;
  document_id?: string;
  location?: string;
  snippet: string;
  quote_hash?: string;
  verified?: boolean;
};

export type ExtractedFact = {
  id: string;
  label: string;
  value: string;
  status: "found" | "missing" | "uncertain";
  citations: Citation[];
};

export type AssessmentSection = {
  title: string;
  conclusion: string;
  confidence: "low" | "medium" | "high";
  reasoning: string;
  citations: Citation[];
  assumptions: string[];
  uncertainties: string[];
};

export type AgentTraceEvent = {
  agent: string;
  action: string;
  output_summary: string;
};

export type AnalysisResult = {
  case_id: string;
  summary: string;
  extracted_facts: ExtractedFact[];
  ai_system_assessment: AssessmentSection;
  risk_classification: AssessmentSection;
  obligations: AssessmentSection[];
  governance_observations: AssessmentSection[];
  missing_information: string[];
  follow_up_questions: string[];
  citations: Citation[];
  agent_trace: AgentTraceEvent[];
  limitation_notice: string;
};

export type ChatMessage = {
  id: string;
  case_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: Citation[];
  created_at: string;
};

export type ChatResponse = {
  role: "assistant";
  content: string;
  citations: Citation[];
  new_facts_detected: string[];
  reassessment_recommended: boolean;
};

export type RuntimeSignal = {
  kind: string;
  value: string;
  severity: "low" | "medium" | "high";
  evidence: string;
};

export type RuntimeNode = {
  id: string;
  label: string;
  kind: string;
  severity: "low" | "medium" | "high";
};

export type RuntimeEdge = {
  source: string;
  target: string;
  label: string;
};

export type RuntimeEvent = {
  time: string;
  actor: string;
  action: string;
  target: string;
  severity: "low" | "medium" | "high";
};

export type RuntimeInspection = {
  filename: string;
  size_bytes: number;
  sha256: string;
  file_type: string;
  entropy: number;
  risk_score: number;
  verdict: "quiet" | "watch" | "hot";
  analysis_mode: "heuristic" | "ai";
  evaluation_basis: string;
  confidence: "low" | "medium" | "high";
  summary: string;
  signals: RuntimeSignal[];
  nodes: RuntimeNode[];
  edges: RuntimeEdge[];
  events: RuntimeEvent[];
  analysis: string[];
  ai_act: RuntimeAIActAssessment;
  signal_reviews: RuntimeSignalReview[];
};

export type RuntimeSignalReview = {
  signal_index: number;
  worker: string;
  kind: string;
  value: string;
  severity: "low" | "medium" | "high";
  review_mode: "heuristic" | "ai";
  verdict: "benign" | "watch" | "hot";
  eu_ai_act_relevance: "none" | "possible" | "likely";
  note: string;
};

export type RuntimeAIActAssessment = {
  relevance: "none" | "possible" | "likely";
  risk_hint:
    | "not_assessable"
    | "minimal_or_unclear"
    | "limited_risk_possible"
    | "high_risk_possible"
    | "prohibited_review_needed";
  confidence: "low" | "medium" | "high";
  summary: string;
  triggers: string[];
  follow_up_questions: string[];
  basis: string;
};

export type RuntimeAIStatus = {
  enabled: boolean;
  ready: boolean;
  provider?: string | null;
  model?: string | null;
  message: string;
};
