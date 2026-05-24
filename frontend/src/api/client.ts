import type {
  AnalysisResult,
  AnalysisRevision,
  Case,
  ChatMessage,
  ChatResponse,
  DocumentRecord,
} from "../types/api";
import {
  mockAnalysis,
  mockCases,
  mockDocuments,
  mockMessages,
} from "./mockData";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";

export type ApiMode = "live" | "mock";
let mode: ApiMode = "live";
const listeners = new Set<(m: ApiMode) => void>();

export function getApiMode(): ApiMode {
  return mode;
}
export function onApiModeChange(cb: (m: ApiMode) => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
function setMode(m: ApiMode) {
  if (mode !== m) {
    mode = m;
    listeners.forEach((cb) => cb(m));
  }
}

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch (e: any) {
    // Network failure → mock fallback
    throw new ApiError(`Network error: ${e?.message ?? "unreachable"}`);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data?.detail || data?.message || JSON.stringify(data);
    } catch {
      try {
        detail = (await res.text()) || detail;
      } catch {}
    }
    throw new ApiError(`HTTP ${res.status}: ${detail}`, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Run a live request; if it's a NETWORK error (backend unreachable), fall back to mock.
 * Real HTTP errors from a reachable backend still propagate. */
async function withFallback<T>(live: () => Promise<T>, fallback: () => T | Promise<T>): Promise<T> {
  try {
    const result = await live();
    setMode("live");
    return result;
  } catch (e) {
    if (e instanceof ApiError && e.status === undefined) {
      // network error
      setMode("mock");
      return fallback();
    }
    throw e;
  }
}

// Simple in-memory mock store mirrors
const mockState = {
  cases: [...mockCases] as Case[],
  docs: JSON.parse(JSON.stringify(mockDocuments)) as Record<string, DocumentRecord[]>,
  analysis: {} as Record<string, AnalysisResult>,
  activeAnalysisId: {} as Record<string, string | undefined>,
  analysisHistory: {} as Record<
    string,
    Array<AnalysisRevision & { result: AnalysisResult }>
  >,
  msgs: { ...mockMessages } as Record<string, ChatMessage[]>,
};

function uid(prefix = "id") {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
}

export function createCase(input: { title: string; description?: string }): Promise<Case> {
  return withFallback(
    () => request<Case>("/cases", { method: "POST", body: JSON.stringify(input) }),
    () => {
      const c: Case = {
        id: uid("case"),
        title: input.title,
        description: input.description ?? null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      mockState.cases.unshift(c);
      return c;
    }
  );
}

export function updateCase(
  caseId: string,
  input: { title?: string; description?: string },
): Promise<Case> {
  return withFallback(
    () => request<Case>(`/cases/${caseId}`, { method: "PATCH", body: JSON.stringify(input) }),
    () => {
      const index = mockState.cases.findIndex((x) => x.id === caseId);
      if (index === -1) throw new ApiError("Case not found", 404);
      if (input.description !== undefined && mockState.analysis[caseId]) {
        const currentDescription = mockState.cases[index].description ?? "";
        if (input.description !== currentDescription) {
          throw new ApiError("Case is locked after analysis", 409);
        }
      }
      const updated = {
        ...mockState.cases[index],
        ...input,
        description: input.description ?? mockState.cases[index].description,
        updated_at: new Date().toISOString(),
      };
      mockState.cases[index] = updated;
      return updated;
    }
  );
}

export function deleteCase(caseId: string): Promise<void> {
  return withFallback(
    () => request<void>(`/cases/${caseId}`, { method: "DELETE" }),
    () => {
      const index = mockState.cases.findIndex((x) => x.id === caseId);
      if (index === -1) throw new ApiError("Case not found", 404);
      mockState.cases.splice(index, 1);
      delete mockState.docs[caseId];
      delete mockState.analysis[caseId];
      delete mockState.activeAnalysisId[caseId];
      delete mockState.analysisHistory[caseId];
      delete mockState.msgs[caseId];
    }
  );
}

export function unlockCaseAnalysis(caseId: string): Promise<void> {
  return withFallback(
    () => request<void>(`/cases/${caseId}/analysis`, { method: "DELETE" }),
    () => {
      const exists = mockState.cases.some((x) => x.id === caseId);
      if (!exists) throw new ApiError("Case not found", 404);
      delete mockState.analysis[caseId];
      delete mockState.activeAnalysisId[caseId];
      delete mockState.msgs[caseId];
    }
  );
}

export function listCases(): Promise<Case[]> {
  return withFallback(
    () => request<Case[]>("/cases"),
    () => mockState.cases
  );
}

export function getCase(caseId: string): Promise<Case & { documents?: DocumentRecord[] }> {
  return withFallback(
    () => request(`/cases/${caseId}`),
    () => {
      const c = mockState.cases.find((x) => x.id === caseId);
      if (!c) throw new ApiError("Case not found", 404);
      return { ...c, documents: mockState.docs[caseId] ?? [] };
    }
  );
}

export function uploadDocuments(caseId: string, files: File[]): Promise<DocumentRecord[]> {
  return withFallback(
    () => {
      const fd = new FormData();
      files.forEach((f) => fd.append("files", f, f.name));
      return request<DocumentRecord[]>(`/cases/${caseId}/documents`, { method: "POST", body: fd });
    },
    () => {
      if (mockState.analysis[caseId]) {
        throw new ApiError("Document uploads are locked after analysis", 409);
      }
      const docs = files.map<DocumentRecord>((f) => ({
        id: uid("doc"),
        case_id: caseId,
        filename: f.name,
        content_type: f.type || null,
        status: "parsed",
        created_at: new Date().toISOString(),
      }));
      mockState.docs[caseId] = [...(mockState.docs[caseId] ?? []), ...docs];
      return docs;
    }
  );
}

export function deleteDocument(caseId: string, documentId: string): Promise<void> {
  return withFallback(
    () => request<void>(`/cases/${caseId}/documents/${documentId}`, { method: "DELETE" }),
    () => {
      if (mockState.analysis[caseId]) {
        throw new ApiError("Unlock the case before removing documents", 409);
      }
      const docs = mockState.docs[caseId] ?? [];
      const nextDocs = docs.filter((doc) => doc.id !== documentId);
      if (nextDocs.length === docs.length) throw new ApiError("Document not found", 404);
      mockState.docs[caseId] = nextDocs;
    }
  );
}

export function listDocuments(caseId: string): Promise<DocumentRecord[]> {
  return withFallback(
    () => request<DocumentRecord[]>(`/cases/${caseId}/documents`),
    () => mockState.docs[caseId] ?? []
  );
}

export function runAnalysis(caseId: string): Promise<AnalysisResult> {
  return withFallback(
    () => request<AnalysisResult>(`/cases/${caseId}/analyze`, { method: "POST" }),
    async () => {
      await new Promise((r) => setTimeout(r, 600));
      const a = mockAnalysis(caseId);
      const id = uid("analysis");
      mockState.analysis[caseId] = a;
      mockState.activeAnalysisId[caseId] = id;
      const existing = mockState.analysisHistory[caseId] ?? [];
      const revision: AnalysisRevision & { result: AnalysisResult } = {
        id,
        case_id: caseId,
        status: "complete",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        revision: existing.length + 1,
        active: true,
        summary: a.summary,
        risk_label: riskLabel(a.risk_classification.conclusion),
        risk_conclusion: a.risk_classification.conclusion,
        confidence: a.risk_classification.confidence,
        result: a,
      };
      mockState.analysisHistory[caseId] = [
        ...existing.map((item) => ({ ...item, active: false })),
        revision,
      ];
      return a;
    }
  );
}

export function getAnalysis(caseId: string): Promise<AnalysisResult | null> {
  return withFallback(
    () => request<AnalysisResult | null>(`/cases/${caseId}/analysis`),
    () => mockState.analysis[caseId] ?? null
  );
}

export function listAnalysisRevisions(caseId: string): Promise<AnalysisRevision[]> {
  return withFallback(
    () => request<AnalysisRevision[]>(`/cases/${caseId}/analyses`),
    () => (mockState.analysisHistory[caseId] ?? []).map(({ result: _result, ...item }) => item)
  );
}

export function getAnalysisRevision(
  caseId: string,
  analysisId: string,
): Promise<AnalysisResult> {
  return withFallback(
    () => request<AnalysisResult>(`/cases/${caseId}/analyses/${analysisId}`),
    () => {
      const revision = (mockState.analysisHistory[caseId] ?? []).find(
        (item) => item.id === analysisId,
      );
      if (!revision) throw new ApiError("Analysis revision not found", 404);
      return revision.result;
    }
  );
}

export function getMessages(caseId: string): Promise<ChatMessage[]> {
  return withFallback(
    () => request<ChatMessage[]>(`/cases/${caseId}/messages`),
    () => mockState.msgs[caseId] ?? []
  );
}

export function sendChatMessage(caseId: string, message: string): Promise<ChatResponse> {
  return withFallback(
    () =>
      request<ChatResponse>(`/cases/${caseId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
      }),
    async () => {
      const arr = mockState.msgs[caseId] ?? [];
      arr.push({
        id: uid("msg"),
        case_id: caseId,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
      });
      const response: ChatResponse = {
        role: "assistant",
        content:
          "Mock response: based on the case so far, your question relates to high-risk obligations. Consider Art. 14 (human oversight) and Art. 10 (data governance).",
        citations: [
          {
            id: uid("c"),
            source_type: "legislation",
            source_title: "Regulation (EU) 2024/1689",
            location: "Art. 14",
            snippet: "High-risk AI systems shall be designed ... such that they can be effectively overseen by natural persons.",
          },
        ],
        new_facts_detected: [],
        reassessment_recommended: /retrain|change|update|new/i.test(message),
      };
      arr.push({
        id: uid("msg"),
        case_id: caseId,
        role: "assistant",
        content: response.content,
        citations: response.citations,
        created_at: new Date().toISOString(),
      });
      mockState.msgs[caseId] = arr;
      return response;
    }
  );
}

function riskLabel(conclusion: string): string {
  const text = conclusion.toLowerCase();
  if (text.includes("prohibited")) return "Prohibited";
  if (text.includes("high-risk") || text.includes("high risk")) return "High risk";
  if (text.includes("limited") || text.includes("transparency")) return "Limited risk";
  if (text.includes("minimal") || text.includes("low")) return "Low risk";
  return "Needs review";
}

export { API_BASE_URL };
