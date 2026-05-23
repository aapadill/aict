import type {
  AnalysisResult,
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
  code?: string;
  constructor(message: string, status?: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
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
    let code: string | undefined;
    try {
      const data = await res.json();
      if (data?.detail && typeof data.detail === "object") {
        detail = data.detail.message || JSON.stringify(data.detail);
        code = data.detail.error;
      } else {
        detail = data?.detail || data?.message || JSON.stringify(data);
      }
    } catch {
      try {
        detail = (await res.text()) || detail;
      } catch {}
    }
    throw new ApiError(`HTTP ${res.status}: ${detail}`, res.status, code);
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
      mockState.analysis[caseId] = a;
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

export async function checkHealth(): Promise<{ status: string; llm_configured: boolean }> {
  return request("/health");
}

export { API_BASE_URL };
