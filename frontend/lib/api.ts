// API client. Reads the base URL from NEXT_PUBLIC_API_BASE_URL, attaches the
// bearer token when present, and unwraps the standard success/error envelope.

import { clearAuth, getToken } from "@/lib/auth";
import type {
  AiProvider,
  AuthToken,
  CalendarEvent,
  ChatGroup,
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
import type { AiProviderUpdatePayload, GoogleScopes } from "@/types/api";

// Resolve the API base URL so the app works across devices without a rebuild:
//  1. If NEXT_PUBLIC_API_BASE_URL is set, always use it.
//  2. Otherwise, in the browser, derive it from the current host (so opening the
//     app at http://<LAN-IP>:3000 on a phone calls the API at http://<LAN-IP>:8000).
//  3. Fall back to localhost (SSR / build time).
function resolveApiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (fromEnv && fromEnv.trim()) return fromEnv.trim();
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
  }
  return "http://localhost:8000/api/v1";
}

export const API_BASE_URL = resolveApiBaseUrl();

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
      "Cannot reach the AllHaven API. Is the backend running?",
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
  updateMe: (payload: { full_name?: string; workspace_name?: string }) =>
    request<Me>("/auth/me", { method: "PATCH", body: json(payload) }),
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
  // Conversations
  listSessions: () => request<ChatSession[]>("/ai/sessions"),
  createSession: (groupId?: string | null, title?: string) =>
    request<ChatSession>("/ai/sessions", {
      method: "POST",
      body: json({ title: title ?? null, group_id: groupId ?? null }),
    }),
  updateSession: (id: string, payload: { title?: string; group_id?: string | null }) =>
    request<ChatSession>(`/ai/sessions/${id}`, { method: "PATCH", body: json(payload) }),
  deleteSession: (id: string) =>
    request<{ id: string }>(`/ai/sessions/${id}`, { method: "DELETE" }),
  // Groups / projects
  listGroups: () => request<ChatGroup[]>("/ai/groups"),
  createGroup: (name: string) =>
    request<ChatGroup>("/ai/groups", { method: "POST", body: json({ name }) }),
  renameGroup: (id: string, name: string) =>
    request<ChatGroup>(`/ai/groups/${id}`, { method: "PATCH", body: json({ name }) }),
  deleteGroup: (id: string) =>
    request<{ id: string }>(`/ai/groups/${id}`, { method: "DELETE" }),
  listMessages: (sessionId: string) =>
    request<ChatMessage[]>(`/ai/sessions/${sessionId}/messages`),
  chat: (message: string, sessionId?: string, providerId?: string) =>
    request<ChatResponse>("/ai/chat", {
      method: "POST",
      body: json({ message, session_id: sessionId || null, provider_id: providerId || null }),
    }),
  // Fan a message out to up to 3 agents concurrently.
  multiChat: (message: string, providerIds: string[], sessionId?: string) =>
    request<MultiChatResponse>("/ai/chat/multi", {
      method: "POST",
      body: json({ message, provider_ids: providerIds, session_id: sessionId || null }),
    }),
  // Run a multi-agent debate: agents argue across `rounds`, then one synthesizes.
  debateChat: (message: string, providerIds: string[], sessionId?: string, rounds = 2) =>
    request<MultiChatResponse>("/ai/chat/debate", {
      method: "POST",
      body: json({ message, provider_ids: providerIds, session_id: sessionId || null, rounds }),
    }),
  getRun: (runId: string) => request<MultiChatResponse>(`/ai/runs/${runId}`),
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
  getPolicy: () => request<AiPolicy>("/ai/policy"),
  setPolicy: (payload: { allow_external?: boolean; default_provider?: string }) =>
    request<AiPolicy>("/ai/policy", { method: "PUT", body: json(payload) }),
};

export interface AiPolicy {
  allow_external: boolean;
  default_provider: string;
  default_privacy_mode: string;
  env_default: boolean;
}

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

// --- Google OAuth foundation ---
export const googleApi = {
  scopes: () => request<GoogleScopes>("/settings/google/scopes"),
  loginUrl: (include?: string[]) =>
    request<{ authorization_url: string; scopes: string[] }>(
      `/auth/google/login${include && include.length ? `?include=${include.join(",")}` : ""}`,
    ),
  disconnect: () => request<Integration>("/settings/google/disconnect", { method: "POST" }),
};

// --- Calendar ---
export const calendarApi = {
  list: () => request<CalendarEvent[]>("/calendar/events"),
  create: (payload: Record<string, unknown>) =>
    request<CalendarEvent>("/calendar/events", { method: "POST", body: json(payload) }),
  update: (id: string, payload: Record<string, unknown>) =>
    request<CalendarEvent>(`/calendar/events/${id}`, { method: "PUT", body: json(payload) }),
  remove: (id: string) =>
    request<{ id: string }>(`/calendar/events/${id}`, { method: "DELETE" }),
};

// --- Drive (file upload uses multipart, not JSON) ---
export const driveApi = {
  list: () => request<DriveFile[]>("/drive/files"),
  upload: async (file: File): Promise<DriveFile> => {
    const token = getToken();
    const form = new FormData();
    form.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/drive/files`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: form,
      });
    } catch {
      throw new ApiException("Cannot reach the AllHaven API. Is the backend running?", "NETWORK_ERROR", 0);
    }
    const body = (await res.json().catch(() => null)) as ApiEnvelope<DriveFile> | null;
    if (!res.ok || body?.status === "error") {
      if (res.status === 401) clearAuth();
      throw new ApiException(body?.message || `Upload failed (${res.status})`, body?.error_code || "HTTP_ERROR", res.status);
    }
    return body?.data as DriveFile;
  },
  downloadUrl: (id: string) => `${API_BASE_URL}/drive/files/${id}/download`,
  remove: (id: string) => request<{ id: string }>(`/drive/files/${id}`, { method: "DELETE" }),
};

// --- Automations ---
export const automationsApi = {
  list: () => request<Automation[]>("/automations"),
  create: (payload: Record<string, unknown>) =>
    request<Automation>("/automations", { method: "POST", body: json(payload) }),
  update: (id: string, payload: Record<string, unknown>) =>
    request<Automation>(`/automations/${id}`, { method: "PUT", body: json(payload) }),
  remove: (id: string) =>
    request<{ id: string }>(`/automations/${id}`, { method: "DELETE" }),
};

// --- Weather ---
export const weatherApi = {
  listLocations: () => request<WeatherLocation[]>("/weather/locations"),
  addLocation: (name: string, isDefault = false) =>
    request<WeatherLocation>("/weather/locations", {
      method: "POST",
      body: json({ name, is_default: isDefault }),
    }),
  removeLocation: (id: string) =>
    request<{ id: string }>(`/weather/locations/${id}`, { method: "DELETE" }),
  current: (location?: string) =>
    request<WeatherCurrent>(`/weather/current${location ? `?location=${encodeURIComponent(location)}` : ""}`),
};
