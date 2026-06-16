// Shared API contracts (mirror the backend Pydantic schemas).

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Me {
  user: User;
  workspace: Workspace;
}

export type TaskStatus = "TODO" | "IN_PROGRESS" | "DONE";
export type TaskPriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

export interface Task {
  id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  checklist_items: ChecklistItem[];
}

export interface ChecklistItem {
  id: string;
  title: string;
  is_done: boolean;
  position: number;
}

export interface Note {
  id: string;
  title: string;
  content: string | null;
  tags: string[];
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export type FinanceType = "INCOME" | "EXPENSE";

export interface FinanceCategory {
  id: string;
  name: string;
  type: FinanceType;
  created_at: string;
}

export interface Transaction {
  id: string;
  type: FinanceType;
  amount: number;
  currency: string;
  category_id: string | null;
  category_name_snapshot: string | null;
  description: string | null;
  transaction_date: string;
  created_at: string;
  updated_at: string;
}

export interface FinanceSummary {
  year: number;
  month: number;
  currency: string;
  total_income: number;
  total_expense: number;
  balance: number;
  transaction_count: number;
}

export interface ChatGroup {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ChatSession {
  id: string;
  title: string | null;
  group_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  session_id: string | null;
  role: "user" | "assistant" | "system";
  content: string;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export interface ChatResponse {
  session_id: string;
  reply: ChatMessage;
  ai_configured: boolean;
}

// Status of mirroring web settings to the local .env file.
export interface EnvSync {
  status: "success" | "failed" | "skipped";
  message: string;
  keys: string[];
  backup: string | null;
}

export type AgentResponseStatus =
  | "queued"
  | "running"
  | "completed"
  | "error"
  | "not_configured"
  | "disabled"
  | "blocked"
  | "unsupported";

// Thinking Mode controls reasoning depth + sampling (separate from chat mode).
export type ThinkingMode = "fast" | "balance" | "thinking" | "deep";

export interface AgentResponse {
  id: string;
  run_id: string;
  provider_id: string;
  provider_name: string;
  status: AgentResponseStatus;
  content: string | null;
  error_message: string | null;
  latency_ms: number | null;
  meta: Record<string, unknown> | null;
  created_at: string;
}

export interface MultiChatResponse {
  run_id: string;
  session_id: string;
  status: "running" | "completed" | "partial" | "error" | "empty";
  agent_responses: AgentResponse[];
}

export interface CalendarEvent {
  id: string;
  title: string;
  description: string | null;
  location: string | null;
  start_at: string;
  end_at: string | null;
  all_day: boolean;
  created_at: string;
  updated_at: string;
}

export interface DriveFile {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface Automation {
  id: string;
  name: string;
  description: string | null;
  trigger_type: string;
  action_type: string;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface WeatherLocation {
  id: string;
  name: string;
  is_default: boolean;
  created_at: string;
}

export interface WeatherCurrent {
  status:
    | "ok"
    | "setup_required"
    | "no_location"
    | "unsupported_provider"
    | "unavailable"
    | "error";
  detail?: string;
  location: string | null;
  temp_c?: number;
  feels_like_c?: number;
  humidity?: number;
  description?: string;
  icon?: string;
  wind_speed?: number;
}

export interface ToolProposal {
  id: string;
  tool_name: string;
  tool_payload: Record<string, unknown>;
  status: string;
  risk_level: string;
  requires_confirmation: boolean;
  created_at: string;
}

export type IntegrationStatusValue =
  | "online"
  | "configured"
  | "not_configured"
  | "error"
  | "unavailable"
  | "disabled"
  // legacy value kept for safety in status colour maps
  | "connected";

export interface FieldSpec {
  key: string;
  label: string;
  secret: boolean;
  required: boolean;
  placeholder: string;
}

export interface SecretPreview {
  configured: boolean;
  preview: string;
}

export interface Integration {
  key: string;
  name: string;
  status: IntegrationStatusValue;
  configured: boolean;
  detail: string;
  // Rich fields (present from the settings endpoints)
  id?: string;
  purpose?: string;
  provider_type?: string;
  group?: string;
  editable?: boolean;
  api_key_required?: boolean;
  enabled?: boolean;
  fields?: FieldSpec[];
  public_config?: Record<string, string>;
  secrets?: Record<string, SecretPreview>;
  last_verified_at?: string | null;
  last_error?: string | null;
  source?: string;
  env_sync?: EnvSync;
}

export interface AiProvider {
  id: string;
  provider_id: string;
  name: string;
  purpose: string;
  provider_type: string;
  external: boolean;
  api_key_required: boolean;
  capabilities?: { text: boolean; image: boolean; tools: boolean };
  enabled: boolean;
  status: IntegrationStatusValue;
  configured: boolean;
  detail: string;
  default_model: string | null;
  privacy_mode: string;
  fields: FieldSpec[];
  public_config: Record<string, string>;
  secrets: Record<string, SecretPreview>;
  last_verified_at: string | null;
  last_error: string | null;
  env_sync?: EnvSync;
}

// --- Live n8n workflows (read + activate/deactivate via the connected n8n) ---
export type N8nStatus = "online" | "not_configured" | "no_api_key" | "unavailable" | "unauthorized" | "error";

export interface N8nWorkflow {
  id: string;
  name: string;
  active: boolean;
  updated_at?: string | null;
}

export interface N8nWorkflowList {
  status: N8nStatus;
  message: string;
  base_url: string;
  workflows: N8nWorkflow[];
}
