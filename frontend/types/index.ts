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

export interface ChatSession {
  id: string;
  title: string | null;
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
  | "connected"
  | "configured"
  | "not_configured"
  | "error";

export interface Integration {
  key: string;
  name: string;
  status: IntegrationStatusValue;
  configured: boolean;
  detail: string;
}
