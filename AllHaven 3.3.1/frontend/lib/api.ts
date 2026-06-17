// API client. Reads the base URL from NEXT_PUBLIC_API_BASE_URL, authenticates
// via the HttpOnly session cookie (credentials: "include" + CSRF header on
// state-changing requests), and unwraps the standard success/error envelope.

import { clearAuth } from "@/lib/auth";
import type {
  AiChatSettings,
  AiMemory,
  AiProvider,
  AiTool,
  AuthToken,
  Automation,
  CalendarEvent,
  ChatGroup,
  ChatMessage,
  ChatResponse,
  ChatSession,
  DriveConfig,
  DriveFile,
  FinanceCategory,
  FinanceReport,
  FinanceSummary,
  Integration,
  KnowledgeDocument,
  KnowledgeSearchResponse,
  Me,
  MemorySettings,
  MemorySuggestion,
  ModelSlot,
  MultiChatResponse,
  N8nWorkflow,
  N8nWorkflowList,
  Note,
  PortsApplyResult,
  ServiceStatus,
  SystemLogs,
  SystemPorts,
  SystemStatus,
  Task,
  ToolProposal,
  Transaction,
  WeatherCurrent,
  WeatherLocation,
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

// The CSRF cookie is intentionally readable: its value must be echoed in the
// X-CSRF-Token header on state-changing requests (double-submit check).
function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)allhaven_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const method = (options.method || "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    const csrf = getCsrfToken();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers, credentials: "include" });
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
  // Revokes the server-side session and clears the auth cookies.
  logout: () => request<{ logged_out: boolean }>("/auth/logout", { method: "POST" }),
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
  listTransactions: (params?: { year?: number; month?: number; currency?: string; start?: string; end?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.year) qs.set("year", String(params.year));
    if (params?.month) qs.set("month", String(params.month));
    if (params?.currency) qs.set("currency", params.currency);
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const query = qs.toString();
    return request<Transaction[]>(`/finance/transactions${query ? `?${query}` : ""}`);
  },
  createTransaction: (payload: Record<string, unknown>) =>
    request<Transaction>("/finance/transactions", { method: "POST", body: json(payload) }),
  updateTransaction: (id: string, payload: Record<string, unknown>) =>
    request<Transaction>(`/finance/transactions/${id}`, { method: "PATCH", body: json(payload) }),
  removeTransaction: (id: string) =>
    request<{ id: string }>(`/finance/transactions/${id}`, { method: "DELETE" }),
  summary: (year: number, month: number, currency = "IDR") =>
    request<FinanceSummary>(
      `/finance/summary?year=${year}&month=${month}&currency=${currency}`,
    ),
  report: (payload: { start: string; end: string; periodType?: string; currency?: string }) =>
    request<FinanceReport>(
      `/finance/report?start=${payload.start}&end=${payload.end}&period_type=${payload.periodType ?? "custom"}&currency=${payload.currency ?? "IDR"}`,
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
  chat: (message: string, sessionId?: string, providerId?: string, sectionKey = "general", thinkingMode = "balance", responseLanguage?: string) =>
    request<ChatResponse>("/ai/chat", {
      method: "POST",
      body: json({ message, session_id: sessionId || null, provider_id: providerId || null, section_key: sectionKey, thinking_mode: thinkingMode, response_language: responseLanguage || null }),
    }),
  // Fan a message out to up to 10 agents concurrently. `images` are data URLs;
  // `thinkingMode` controls reasoning depth + sampling.
  multiChat: (message: string, providerIds: string[], sessionId?: string, images?: string[], thinkingMode = "balance", sectionKey = "general", responseLanguage?: string) =>
    request<MultiChatResponse>("/ai/chat/multi", {
      method: "POST",
      body: json({ message, provider_ids: providerIds, session_id: sessionId || null, images: images?.length ? images : null, thinking_mode: thinkingMode, section_key: sectionKey, response_language: responseLanguage || null }),
    }),
  // Run a multi-agent debate: agents argue across `rounds`, then one synthesizes.
  debateChat: (message: string, providerIds: string[], sessionId?: string, rounds = 2, images?: string[], thinkingMode = "balance", sectionKey = "general", responseLanguage?: string) =>
    request<MultiChatResponse>("/ai/chat/debate", {
      method: "POST",
      body: json({ message, provider_ids: providerIds, session_id: sessionId || null, rounds, images: images?.length ? images : null, thinking_mode: thinkingMode, section_key: sectionKey, response_language: responseLanguage || null }),
    }),
  // Run the reasoning council (Analyst -> Critic -> Synthesizer + quality gate).
  reasonChat: (message: string, providerIds: string[], sessionId?: string, thinkingMode = "balance", images?: string[], sectionKey = "general", responseLanguage?: string) =>
    request<MultiChatResponse>("/ai/chat/reason", {
      method: "POST",
      body: json({ message, provider_ids: providerIds, session_id: sessionId || null, thinking_mode: thinkingMode, images: images?.length ? images : null, section_key: sectionKey, response_language: responseLanguage || null }),
    }),
  getRun: (runId: string) => request<MultiChatResponse>(`/ai/runs/${runId}`),
  listProposals: () => request<ToolProposal[]>("/ai/proposals"),
  rejectProposal: (id: string) =>
    request<ToolProposal>(`/ai/proposals/${id}/reject`, { method: "POST" }),
  approveProposal: (id: string) =>
    request<ProposalApproval>(`/ai/proposals/${id}/approve`, { method: "POST" }),
  editProposal: (id: string, toolPayload: Record<string, unknown>) =>
    request<ToolProposal>(`/ai/proposals/${id}`, { method: "PATCH", body: json({ tool_payload: toolPayload }) }),
  // AI tools (registry)
  listTools: (sectionKey?: string) => request<AiTool[]>(`/ai/tools${sectionKey ? `?section_key=${encodeURIComponent(sectionKey)}` : ""}`),
  setToolEnabled: (name: string, enabled: boolean) =>
    request<AiTool>(`/ai/tools/${name}`, { method: "PUT", body: json({ enabled }) }),
  // Chat behavior settings
  getChatSettings: () => request<AiChatSettings>("/ai/settings/chat"),
  setChatSettings: (payload: Partial<AiChatSettings>) =>
    request<AiChatSettings>("/ai/settings/chat", { method: "PUT", body: json(payload) }),
  // Model slots
  saveModelSlots: (providerId: string, slots: Partial<ModelSlot>[]) =>
    request<AiProvider>(`/ai/providers/${providerId}/slots`, { method: "PUT", body: json({ slots }) }),
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
  env_sync?: import("@/types").EnvSync;
}

// --- AI Memory ---
export const memoryApi = {
  list: (category?: string, status = "active") => {
    const params = new URLSearchParams();
    if (category) params.set("category", category);
    if (status !== "active") params.set("status", status);
    const qs = params.toString();
    return request<AiMemory[]>(`/ai/memory${qs ? `?${qs}` : ""}`);
  },
  create: (payload: { category: string; title: string; content: string; sensitivity?: string }) =>
    request<AiMemory>("/ai/memory", { method: "POST", body: json(payload) }),
  search: (q: string) =>
    request<AiMemory[]>(`/ai/memory/search?q=${encodeURIComponent(q)}`),
  update: (id: string, payload: { title?: string; content?: string; category?: string }) =>
    request<AiMemory>(`/ai/memory/${id}`, { method: "PATCH", body: json(payload) }),
  remove: (id: string) =>
    request<{ id: string }>(`/ai/memory/${id}`, { method: "DELETE" }),
  enable: (id: string) =>
    request<AiMemory>(`/ai/memory/${id}/enable`, { method: "POST" }),
  disable: (id: string) =>
    request<AiMemory>(`/ai/memory/${id}/disable`, { method: "POST" }),
  listSuggestions: () =>
    request<MemorySuggestion[]>("/ai/memory/suggestions"),
  approveSuggestion: (id: string) =>
    request<AiMemory>(`/ai/memory/suggestions/${id}/approve`, { method: "POST" }),
  rejectSuggestion: (id: string) =>
    request<{ id: string }>(`/ai/memory/suggestions/${id}/reject`, { method: "POST" }),
  getSettings: () =>
    request<MemorySettings>("/ai/memory/settings"),
  updateSettings: (payload: Partial<MemorySettings>) =>
    request<MemorySettings>("/ai/memory/settings", { method: "PUT", body: json(payload) }),
  clearAll: () =>
    request<{ deleted: number }>("/ai/memory/clear", { method: "POST" }),
  syncSupabase: () =>
    request<{ status: string; message: string }>("/ai/memory/sync/supabase", { method: "POST" }),
};

export interface ProposalApproval {
  proposal: ToolProposal;
  result: Record<string, unknown>;
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

// --- Calendar / Routines ---
export const calendarApi = {
  list: () => request<CalendarEvent[]>("/calendar/events"),
  create: (payload: Record<string, unknown>) =>
    request<CalendarEvent>("/calendar/events", { method: "POST", body: json(payload) }),
  update: (id: string, payload: Record<string, unknown>) =>
    request<CalendarEvent>(`/calendar/events/${id}`, { method: "PUT", body: json(payload) }),
  remove: (id: string) =>
    request<{ id: string }>(`/calendar/events/${id}`, { method: "DELETE" }),
};

export const routinesApi = {
  list: async (params?: { start?: string; end?: string }) => {
    const query = params && (params.start || params.end)
      ? `?${new URLSearchParams(
          Object.entries(params).filter(([, v]) => Boolean(v)) as [string, string][],
        ).toString()}`
      : "";
    try {
      return await request<CalendarEvent[]>(`/routines/events${query}`);
    } catch (err) {
      if (err instanceof ApiException && err.statusCode === 404) {
        return request<CalendarEvent[]>(`/calendar/events${query}`);
      }
      throw err;
    }
  },
  create: async (payload: Record<string, unknown>) => {
    try {
      return await request<CalendarEvent>("/routines/events", { method: "POST", body: json(payload) });
    } catch (err) {
      if (err instanceof ApiException && err.statusCode === 404) {
        return request<CalendarEvent>("/calendar/events", { method: "POST", body: json(payload) });
      }
      throw err;
    }
  },
  update: async (id: string, payload: Record<string, unknown>) => {
    try {
      return await request<CalendarEvent>(`/routines/events/${id}`, { method: "PUT", body: json(payload) });
    } catch (err) {
      if (err instanceof ApiException && err.statusCode === 404) {
        return request<CalendarEvent>(`/calendar/events/${id}`, { method: "PUT", body: json(payload) });
      }
      throw err;
    }
  },
  remove: async (id: string) => {
    try {
      return await request<{ id: string }>(`/routines/events/${id}`, { method: "DELETE" });
    } catch (err) {
      if (err instanceof ApiException && err.statusCode === 404) {
        return request<{ id: string }>(`/calendar/events/${id}`, { method: "DELETE" });
      }
      throw err;
    }
  },
};

// --- Drive (file upload uses multipart, not JSON) ---
export const driveApi = {
  config: () => request<DriveConfig>("/drive/config"),
  list: () => request<DriveFile[]>("/drive/files"),
  upload: async (file: File): Promise<DriveFile> => {
    const form = new FormData();
    form.append("file", file);
    const csrf = getCsrfToken();
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/drive/files`, {
        method: "POST",
        headers: csrf ? { "X-CSRF-Token": csrf } : undefined,
        body: form,
        credentials: "include",
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


// --- AI Knowledge ---
export const knowledgeApi = {
  listDocuments: () => request<KnowledgeDocument[]>("/ai/knowledge/documents"),
  uploadDocument: async (file: File, title?: string): Promise<KnowledgeDocument> => {
    const form = new FormData();
    form.append("file", file);
    const csrf = getCsrfToken();
    const qs = title?.trim() ? `?title=${encodeURIComponent(title.trim())}` : "";
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/ai/knowledge/documents${qs}`, {
        method: "POST",
        headers: csrf ? { "X-CSRF-Token": csrf } : undefined,
        body: form,
        credentials: "include",
      });
    } catch {
      throw new ApiException("Cannot reach the AllHaven API. Is the backend running?", "NETWORK_ERROR", 0);
    }
    const body = (await res.json().catch(() => null)) as ApiEnvelope<KnowledgeDocument> | null;
    if (!res.ok || body?.status === "error") {
      if (res.status === 401) clearAuth();
      throw new ApiException(body?.message || `Upload failed (${res.status})`, body?.error_code || "HTTP_ERROR", res.status);
    }
    return body?.data as KnowledgeDocument;
  },
  search: (q: string, limit = 5) =>
    request<KnowledgeSearchResponse>(`/ai/knowledge/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  reindex: (id: string) =>
    request<KnowledgeDocument>(`/ai/knowledge/documents/${id}/reindex`, { method: "POST" }),
  remove: (id: string) =>
    request<{ id: string }>(`/ai/knowledge/documents/${id}`, { method: "DELETE" }),
};

// --- Live n8n workflows (read + activate/deactivate the connected n8n) ---
export const n8nApi = {
  listWorkflows: () => request<N8nWorkflowList>("/n8n/workflows"),
  setActive: (id: string, active: boolean) =>
    request<N8nWorkflow>(`/n8n/workflows/${id}/active`, { method: "POST", body: json({ active }) }),
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

// --- System Control (start/stop/restart & inspect Haven services) ---
export const systemApi = {
  status: () => request<SystemStatus>("/system/status"),
  action: (name: string, action: string) =>
    request<ServiceStatus>(`/system/services/${name}/${action}`, { method: "POST", body: json({}) }),
  logs: (name: string, lines = 300) => request<SystemLogs>(`/system/logs/${name}?lines=${lines}`),
  getPorts: () => request<SystemPorts>("/system/ports"),
  savePorts: (ports: Record<string, number>, restart: boolean) =>
    request<PortsApplyResult>(`/system/ports?restart=${restart}`, { method: "POST", body: json(ports) }),
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
