// API client. Reads the base URL from NEXT_PUBLIC_API_BASE_URL, attaches the
// bearer token when present, and unwraps the standard success/error envelope.

import { clearAuth, getToken } from "@/lib/auth";
import type {
  AiProvider,
  AuthToken,
  ChatMessage,
  ChatResponse,
  ChatSession,
  FinanceCategory,
  FinanceSummary,
  Integration,
  Me,
  Note,
  Task,
  ToolProposal,
  Transaction,
} from "@/types";
import type { AiProviderUpdatePayload } from "@/types/api";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiException extends Error {
  code: string;
  statusCode: number;
  details: unknown;

  constructor(message: string, code: string, statusCode: number, details?: unknown) {
    super(message);
    this.name = "ApiException";
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}

interface ApiEnvelope<T> {
  status: "success" | "error";
  data?: T;
  message?: string;
  error_code?: string;
  details?: unknown;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiException(
      "Cannot reach the CoreOS API. Is the backend running?",
      "NETWORK_ERROR",
      0,
    );
  }

  let body: ApiEnvelope<T> | null = null;
  try {
    body = (await res.json()) as ApiEnvelope<T>;
  } catch {
    body = null;
  }

  if (!res.ok || body?.status === "error") {
    if (res.status === 401) clearAuth();
    throw new ApiException(
      body?.message || `Request failed (${res.status})`,
      body?.error_code || "HTTP_ERROR",
      res.status,
      body?.details,
    );
  }

  return (body?.data ?? null) as T;
}

const json = (payload: unknown) => JSON.stringify(payload);

// --- Auth ---
export const authApi = {
  register: (email: string, password: string, full_name?: string) =>
    request<AuthToken>("/auth/register", {
      method: "POST",
      body: json({ email, password, full_name: full_name || null }),
    }),
  login: (email: string, password: string) =>
    request<AuthToken>("/auth/login", { method: "POST", body: json({ email, password }) }),
  me: () => request<Me>("/auth/me"),
};

// --- Tasks ---
export const tasksApi = {
  list: () => request<Task[]>("/tasks"),
  create: (payload: Record<string, unknown>) =>
    request<Task>("/tasks", { method: "POST", body: json(payload) }),
  update: (id: string, payload: Partial<Task>) =>
    request<Task>(`/tasks/${id}`, { method: "PATCH", body: json(payload) }),
  remove: (id: string) => request<{ id: string }>(`/tasks/${id}`, { method: "DELETE" }),
  complete: (id: string) => request<Task>(`/tasks/${id}/complete`, { method: "POST" }),
  reopen: (id: string) => request<Task>(`/tasks/${id}/reopen`, { method: "POST" }),
  addChecklistItem: (id: string, title: string) =>
    request<Task>(`/tasks/${id}/checklist`, { method: "POST", body: json({ title }) }),
  updateChecklistItem: (id: string, itemId: string, payload: { title?: string; is_done?: boolean }) =>
    request<Task>(`/tasks/${id}/checklist/${itemId}`, { method: "PATCH", body: json(payload) }),
  deleteChecklistItem: (id: string, itemId: string) =>
    request<Task>(`/tasks/${id}/checklist/${itemId}`, { method: "DELETE" }),
};

// --- Notes ---
export const notesApi = {
  list: () => request<Note[]>("/notes"),
  create: (payload: Partial<Note>) =>
    request<Note>("/notes", { method: "POST", body: json(payload) }),
  update: (id: string, payload: Partial<Note>) =>
    request<Note>(`/notes/${id}`, { method: "PATCH", body: json(payload) }),
  remove: (id: string) => request<{ id: string }>(`/notes/${id}`, { method: "DELETE" }),
};

// --- Finance ---
export const financeApi = {
  listCategories: () => request<FinanceCategory[]>("/finance/categories"),
  createCategory: (payload: { name: string; type: string }) =>
    request<FinanceCategory>("/finance/categories", { method: "POST", body: json(payload) }),
  removeCategory: (id: string) =>
    request<{ id: string }>(`/finance/categories/${id}`, { method: "DELETE" }),
  listTransactions: () => request<Transaction[]>("/finance/transactions"),
  createTransaction: (payload: Record<string, unknown>) =>
    request<Transaction>("/finance/transactions", { method: "POST", body: json(payload) }),
  removeTransaction: (id: string) =>
    request<{ id: string }>(`/finance/transactions/${id}`, { method: "DELETE" }),
  summary: (year: number, month: number, currency = "IDR") =>
    request<FinanceSummary>(
      `/finance/summary?year=${year}&month=${month}&currency=${currency}`,
    ),
};

// --- AI ---
export const aiApi = {
  listSessions: () => request<ChatSession[]>("/ai/sessions"),
  listMessages: (sessionId: string) =>
    request<ChatMessage[]>(`/ai/sessions/${sessionId}/messages`),
  chat: (message: string, sessionId?: string, providerId?: string) =>
    request<ChatResponse>("/ai/chat", {
      method: "POST",
      body: json({ message, session_id: sessionId || null, provider_id: providerId || null }),
    }),
  listProposals: () => request<ToolProposal[]>("/ai/proposals"),
  rejectProposal: (id: string) =>
    request<ToolProposal>(`/ai/proposals/${id}/reject`, { method: "POST" }),
  // AI provider configuration
  listProviders: () => request<{ providers: AiProvider[] }>("/ai/providers"),
  saveProvider: (id: string, payload: AiProviderUpdatePayload) =>
    request<AiProvider>(`/ai/providers/${id}`, { method: "PUT", body: json(payload) }),
  testProvider: (id: string) =>
    request<AiProvider>(`/ai/providers/${id}/test`, { method: "POST" }),
  enableProvider: (id: string) =>
    request<AiProvider>(`/ai/providers/${id}/enable`, { method: "POST" }),
  disableProvider: (id: string) =>
    request<AiProvider>(`/ai/providers/${id}/disable`, { method: "POST" }),
  getPolicy: () =>
    request<{ allow_external: boolean; default_privacy_mode: string; env_default: boolean }>(
      "/ai/policy",
    ),
  setPolicy: (allow_external: boolean) =>
    request<{ allow_external: boolean; default_privacy_mode: string; env_default: boolean }>(
      "/ai/policy",
      { method: "PUT", body: json({ allow_external }) },
    ),
};

// --- Settings ---
export const settingsApi = {
  integrations: () => request<{ integrations: Integration[] }>("/settings/integrations"),
  getIntegration: (id: string) => request<Integration>(`/settings/integrations/${id}`),
  saveIntegration: (id: string, public_config: Record<string, string>, secrets: Record<string, string>) =>
    request<Integration>(`/settings/integrations/${id}`, {
      method: "PUT",
      body: json({ public_config, secrets }),
    }),
  testIntegration: (id: string) =>
    request<Integration>(`/settings/integrations/${id}/test`, { method: "POST" }),
  enableIntegration: (id: string) =>
    request<Integration>(`/settings/integrations/${id}/enable`, { method: "POST" }),
  disableIntegration: (id: string) =>
    request<Integration>(`/settings/integrations/${id}/disable`, { method: "POST" }),
  clearIntegration: (id: string) =>
    request<Integration>(`/settings/integrations/${id}`, { method: "DELETE" }),
};
