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

// A selectable model slot on a provider (OpenRouter agents: 1 slot each; every
// other provider: 2 slots — slot 2 is an optional secondary model). `ref` is the
// agent reference used in multi-agent runs (e.g. "anthropic#2").
export interface ModelSlot {
  slot: number;
  ref: string;
  model: string;
  role: string;
  enabled: boolean;
  configured: boolean;
}

// One registered AI tool (backend Tool Registry).
export interface AiTool {
  name: string;
  description: string;
  module: string;
  access: "read" | "write";
  risk: "LOW" | "MEDIUM" | "HIGH";
  approval_required: boolean;
  enabled: boolean;
}

// Workspace chat behavior settings.
export interface AiChatSettings {
  default_mode: "single" | "parallel" | "debate" | "reasoning";
  show_debate_flow: boolean;
  require_approval: boolean;
  show_tool_activity: boolean;
  polish_level: "standard" | "high";
  max_active_agents: number;
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
  model_slots?: ModelSlot[];
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

// --- System Control (start/stop/restart & inspect Haven services) ---
export type ServiceName = "backend" | "frontend" | "postgres" | "n8n" | "ollama" | "redis";
export type ServiceState = "running" | "stopped" | "error" | "unavailable" | "unknown";

export interface ServiceStatus {
  name: ServiceName;
  label: string;
  kind: "host" | "docker";
  status: ServiceState;
  port: number | null;
  controllable: boolean;
  actions: string[]; // subset of ["start","stop","restart","logs"]
  message: string;
  last_checked: string; // ISO timestamp
}

export interface SystemStatus {
  agent: { running: boolean; message: string };
  control_enabled: boolean;
  services: ServiceStatus[];
}

export interface SystemLogs {
  name: string;
  content: string;
  truncated: boolean;
  message: string;
}

export interface SystemPorts {
  ports: Record<string, number>;
  defaults: Record<string, number>;
  editable: boolean;
}

export interface PortsApplyResult {
  ports: Record<string, number>;
  restart_required: boolean;
  applied: boolean;
  message: string;
}

// --- AI Memory ---
export type MemoryCategory = "Profile" | "Preferences" | "Projects" | "WorkStyle" | "Technical" | "Goals";
export type MemorySensitivity = "LOW" | "MEDIUM" | "HIGH";
export type MemorySource = "chat_extracted" | "manual" | "llm_extracted";

export interface AiMemory {
  id: string;
  category: MemoryCategory;
  title: string;
  content: string;
  source: MemorySource;
  status: string;
  sensitivity: MemorySensitivity;
  enabled: boolean;
  confidence: number;
  relevance_score: number;
  last_used_at: string | null;
  source_session_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemorySuggestion {
  id: string;
  memory_id: string | null;
  category: MemoryCategory;
  title: string;
  content: string;
  source_session_id: string | null;
  source_snippet: string | null;
  confidence: number;
  sensitivity: MemorySensitivity;
  extraction_method: "rule_based" | "llm";
  status: string;
  created_at: string;
}

export interface MemorySettings {
  auto_learning_enabled: boolean;
  require_approval_sensitive: boolean;
}
