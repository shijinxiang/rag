"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export interface UserInfo {
  id: string;
  username: string;
  role: string;
  department: string | null;
}

interface Tokens {
  access_token: string;
  refresh_token: string;
  user: UserInfo;
}

function authorization(): Record<string, string> {
  const token = sessionStorage.getItem("rag_access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function logout() {
  sessionStorage.removeItem("rag_access_token");
  sessionStorage.removeItem("rag_refresh_token");
}

export async function authenticate(username: string, password: string, email?: string, department?: string): Promise<UserInfo> {
  const tokens = await request<Tokens>(email ? "/auth/register" : "/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password, email, department }),
  });
  sessionStorage.setItem("rag_access_token", tokens.access_token);
  sessionStorage.setItem("rag_refresh_token", tokens.refresh_token);
  return tokens.user;
}

export async function currentUser(): Promise<UserInfo> {
  return request<UserInfo>("/auth/me");
}

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const token = sessionStorage.getItem("rag_refresh_token");
      if (!token) return false;
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: token }),
      });
      if (!response.ok) { logout(); return false; }
      const tokens: Tokens = await response.json();
      sessionStorage.setItem("rag_access_token", tokens.access_token);
      sessionStorage.setItem("rag_refresh_token", tokens.refresh_token);
      return true;
    })().finally(() => { refreshing = null; });
  }
  return refreshing;
}

async function authenticatedFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const send = () => {
    const headers = new Headers(options.headers);
    Object.entries(authorization()).forEach(([name, value]) => headers.set(name, value));
    return fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  };
  let response = await send();
  if (response.status === 401 && !["/auth/login", "/auth/register", "/auth/refresh"].includes(endpoint) && await refreshTokens()) {
    response = await send();
  }
  return response;
}

// ============================================================================
// Types
// ============================================================================

export interface Source {
  index: number;
  doc_title: string;
  doc_id: string;
  chunk_id: string;
  page_number: number | null;
  score: number;
  excerpt: string;
}

export interface QueryResult {
  query_id: string;
  question: string;
  answer: string;
  sources: Source[];
  retrieval_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface DocumentInfo {
  id: string;
  title: string;
  file_type: string;
  file_size: number;
  status: string;
  version: number;
  department: string | null;
  access_level: number;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentList {
  items: DocumentInfo[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface HealthStatus {
  status: string;
  version: string;
  environment: string;
}

// ============================================================================
// API Client
// ============================================================================

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await authenticatedFetch(endpoint, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message =
      body?.error?.message || body?.detail || `HTTP ${res.status}`;
    throw new Error(message);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ============================================================================
// Health
// ============================================================================

export async function healthCheck(): Promise<HealthStatus> {
  return request<HealthStatus>("/health");
}

// ============================================================================
// Documents
// ============================================================================

export async function uploadDocument(
  file: File,
  department?: string,
  accessLevel?: number
): Promise<DocumentInfo> {
  const formData = new FormData();
  formData.append("file", file);

  let endpoint = "/documents/upload";
  const params = new URLSearchParams();
  if (department) params.set("department", department);
  if (accessLevel !== undefined) params.set("access_level", String(accessLevel));
  const qs = params.toString();
  if (qs) endpoint += `?${qs}`;

  const res = await authenticatedFetch(endpoint, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || `Upload failed: HTTP ${res.status}`);
  }

  return res.json();
}

export async function listDocuments(
  page = 1,
  pageSize = 20,
  department?: string,
  status?: string
): Promise<DocumentList> {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (department) params.set("department", department);
  if (status) params.set("status", status);
  return request<DocumentList>(`/documents?${params.toString()}`);
}

export async function getDocument(docId: string): Promise<DocumentInfo> {
  return request<DocumentInfo>(`/documents/${docId}`);
}

export async function deleteDocument(docId: string): Promise<void> {
  return request<void>(`/documents/${docId}`, { method: "DELETE" });
}

// ============================================================================
// Queries
// ============================================================================

export async function askQuestion(
  question: string,
  topK?: number,
  department?: string
): Promise<QueryResult> {
  return request<QueryResult>("/queries", {
    method: "POST",
    body: JSON.stringify({
      question,
      top_k: topK,
      department,
      stream: false,
    }),
  });
}

export async function streamQuestion(
  question: string,
  onSources: (sources: Source[]) => void,
  onToken: (token: string) => void,
  onDone: () => void,
  onError?: (error: Error) => void,
  topK?: number,
  department?: string
): Promise<void> {
  const res = await authenticatedFetch("/queries/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      top_k: topK,
      department,
      stream: true,
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || `Stream error: HTTP ${res.status}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No readable stream");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const lines = frame.split("\n");
      const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
      const data = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).replace(/^ /, "")).join("\n");
      if (event === "sources") onSources(JSON.parse(data));
      else if (event === "token") onToken(data);
      else if (event === "error") { const error = new Error(JSON.parse(data).message); onError?.(error); throw error; }
    }
  }

  onDone();
}

export async function documentAction(id: string, action: "retry" | "review") {
  return request(`/documents/${id}/${action}`, { method: "POST" });
}

export interface Review { id: string; action: string; status: string; payload: Record<string, string>; }
export interface Audit { id: string; action: string; outcome: string; created_at: string; resource_id: string; }
export async function reviews(): Promise<Review[]> { return request("/admin/reviews"); }
export async function audits(): Promise<Audit[]> { return request("/admin/audit-logs"); }
export async function decideReview(id: string, decision: "approve" | "reject") { return request(`/admin/reviews/${id}/${decision}`, { method: "POST", body: JSON.stringify({}) }); }
export interface OpenAISettings { configured: boolean; masked: string | null; restart_required?: boolean; }
export async function getOpenAISettings(): Promise<OpenAISettings> { return request("/admin/settings/openai"); }
export async function updateOpenAISettings(api_key: string): Promise<OpenAISettings> { return request("/admin/settings/openai", { method: "PUT", body: JSON.stringify({ api_key }) }); }

// ============================================================================
// Retrieve Only (Debug)
// ============================================================================

export async function retrieveDocuments(
  question: string,
  topK?: number,
  department?: string
): Promise<{
  query: string;
  results: Array<{
    content: string;
    doc_title: string;
    doc_id: string;
    page_number: number | null;
    score: number;
  }>;
  count: number;
}> {
  return request("/queries/retrieve", {
    method: "POST",
    body: JSON.stringify({
      question,
      top_k: topK,
      department,
    }),
  });
}
