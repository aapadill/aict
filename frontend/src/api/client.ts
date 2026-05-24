import type {
  AnalysisResult,
  AnalysisRevision,
  Case,
  ChatMessage,
  ChatResponse,
  DocumentRecord,
} from "../types/api";

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";

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
    throw new ApiError(`Network error: ${e?.message ?? "backend unreachable"}`);
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

export function createCase(input: { title: string; description?: string }): Promise<Case> {
  return request<Case>("/cases", { method: "POST", body: JSON.stringify(input) });
}

export function updateCase(
  caseId: string,
  input: { title?: string; description?: string },
): Promise<Case> {
  return request<Case>(`/cases/${caseId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteCase(caseId: string): Promise<void> {
  return request<void>(`/cases/${caseId}`, { method: "DELETE" });
}

export function unlockCaseAnalysis(caseId: string): Promise<void> {
  return request<void>(`/cases/${caseId}/analysis`, { method: "DELETE" });
}

export function listCases(): Promise<Case[]> {
  return request<Case[]>("/cases");
}

export function getCase(caseId: string): Promise<Case & { documents?: DocumentRecord[] }> {
  return request<Case & { documents?: DocumentRecord[] }>(`/cases/${caseId}`);
}

export function uploadDocuments(caseId: string, files: File[]): Promise<DocumentRecord[]> {
  const fd = new FormData();
  files.forEach((file) => fd.append("files", file, file.name));
  return request<DocumentRecord[]>(`/cases/${caseId}/documents`, {
    method: "POST",
    body: fd,
  });
}

export function deleteDocument(caseId: string, documentId: string): Promise<void> {
  return request<void>(`/cases/${caseId}/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function listDocuments(caseId: string): Promise<DocumentRecord[]> {
  return request<DocumentRecord[]>(`/cases/${caseId}/documents`);
}

export function runAnalysis(caseId: string): Promise<AnalysisResult> {
  return request<AnalysisResult>(`/cases/${caseId}/analyze`, { method: "POST" });
}

export function getAnalysis(caseId: string): Promise<AnalysisResult | null> {
  return request<AnalysisResult | null>(`/cases/${caseId}/analysis`);
}

export function listAnalysisRevisions(caseId: string): Promise<AnalysisRevision[]> {
  return request<AnalysisRevision[]>(`/cases/${caseId}/analyses`);
}

export function getAnalysisRevision(
  caseId: string,
  analysisId: string,
): Promise<AnalysisResult> {
  return request<AnalysisResult>(`/cases/${caseId}/analyses/${analysisId}`);
}

export function getMessages(caseId: string): Promise<ChatMessage[]> {
  return request<ChatMessage[]>(`/cases/${caseId}/messages`);
}

export function sendChatMessage(caseId: string, message: string): Promise<ChatResponse> {
  return request<ChatResponse>(`/cases/${caseId}/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export { API_BASE_URL };
