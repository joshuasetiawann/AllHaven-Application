// frontend/lib/apiSupabase.ts — Supabase-backed seam. Groups are replaced with real
// Supabase impls task-by-task in later pairs; until then they passthrough to REST.
//
// Compute/file groups (ai/memory/knowledge/drive/system/n8n/google/settings) are NOT
// ported in 3.7 — re-export the REST impl (they are hidden on mobile UI).
export {
  calendarApi,
  routinesApi,
  weatherApi,
  automationsApi,
  aiApi,
  memoryApi,
  knowledgeApi,
  driveApi,
  systemApi,
  n8nApi,
  googleApi,
  settingsApi,
} from "@/lib/apiRest";

// ─── Task 3: authApi (Supabase Auth + workspace bootstrap) ───────────────────

import type { AuthToken, Me, User, Workspace } from "@/types";
import { ApiException } from "@/lib/apiRest";
import { getSupabase, getWorkspaceId, setWorkspaceId, getAppUserId, setAppUserId } from "@/lib/supabaseClient";
import { toApiException } from "@/lib/supabaseError";

async function loadMe(): Promise<Me> {
  const sb = await getSupabase();
  const { data: auth, error: ae } = await sb.auth.getUser();
  if (ae || !auth?.user) throw toApiException(ae ?? { status: 401, message: "Not authenticated" }, 401);
  // RLS returns only this user's profile (profiles.id = app_user_id()).
  const { data: profile, error: pe } = await sb.from("profiles").select("*").single();
  if (pe) throw toApiException(pe);
  setAppUserId(profile.id);
  // Resolve the user's OWNED workspace (matches backend auth_service.get_default_workspace).
  // RLS policy p_owner restricts workspaces to rows where owner_id = app_user_id().
  const { data: ws, error: we } = await sb
    .from("workspaces").select("*")
    .order("created_at", { ascending: true }).limit(1).single();
  if (we) throw toApiException(we);
  setWorkspaceId((ws as { id: string }).id);
  const user: User = {
    id: profile.id,
    email: auth.user.email ?? (profile as any).email ?? "",
    full_name: profile.full_name ?? null,
    created_at: profile.created_at,
  };
  return { user, workspace: ws as Workspace };
}

export const authApi = {
  register: async (): Promise<AuthToken> => {
    throw new ApiException(
      "Create your account on the AllHaven desktop app, then sign in here.",
      "REGISTER_ON_DESKTOP", 501, null,
    );
  },
  login: async (email: string, password: string): Promise<AuthToken> => {
    const sb = await getSupabase();
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) throw toApiException(error, 401);
    const meResult = await loadMe();
    return {
      access_token: data.session?.access_token ?? "",
      token_type: "bearer",
      user: meResult.user,
    };
  },
  logout: async (): Promise<{ logged_out: boolean }> => {
    const sb = await getSupabase();
    await sb.auth.signOut();
    setWorkspaceId(null);
    setAppUserId(null);
    return { logged_out: true };
  },
  me: (): Promise<Me> => loadMe(),
  updateMe: async (payload: { full_name?: string; workspace_name?: string }): Promise<Me> => {
    const sb = await getSupabase();
    // Populate cache if me() hasn't been called yet.
    if (!getAppUserId() || !getWorkspaceId()) await loadMe();
    if (payload.full_name !== undefined) {
      const { error } = await sb.from("profiles").update({ full_name: payload.full_name }).eq("id", getAppUserId()!);
      if (error) throw toApiException(error);
    }
    if (payload.workspace_name !== undefined) {
      const { error } = await sb.from("workspaces").update({ name: payload.workspace_name }).eq("id", getWorkspaceId()!);
      if (error) throw toApiException(error);
    }
    return loadMe();
  },
};

// ─── Task 4: tasksApi (CRUD + complete/reopen + checklist ops) ────────────────

import type { Task } from "@/types";

const TASK_SELECT = "*, checklist_items:task_checklist_items(*)";

// DB rows for task_checklist_items include is_deleted; the frontend ChecklistItem
// type omits it. Use this extended type locally and strip the field before returning.
type DbChecklistItem = { id: string; title: string; is_done: boolean; position: number; is_deleted?: boolean };
type DbTask = Omit<Task, "checklist_items"> & { checklist_items: DbChecklistItem[] };

function stripDeletedItems(task: DbTask): Task {
  return {
    ...task,
    checklist_items: task.checklist_items
      .filter((c) => !c.is_deleted)
      .map(({ is_deleted: _omit, ...rest }) => rest),
  } as Task;
}

async function fetchTask(id: string): Promise<Task> {
  const sb = await getSupabase();
  const { data, error } = await sb.from("tasks").select(TASK_SELECT).eq("id", id).single();
  if (error) throw toApiException(error);
  return stripDeletedItems(data as DbTask);
}

export const tasksApi = {
  list: async (): Promise<Task[]> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("tasks")
      .select(TASK_SELECT)
      .eq("is_deleted", false)
      .order("created_at", { ascending: false });
    if (error) throw toApiException(error);
    return (data ?? []).map((row) => stripDeletedItems(row as DbTask));
  },
  create: async (payload: Record<string, unknown>): Promise<Task> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("tasks")
      .insert({ status: "TODO", priority: "NORMAL", ...payload, workspace_id: getWorkspaceId(), created_by: getAppUserId() })
      .select("id")
      .single();
    if (error) throw toApiException(error);
    return fetchTask((data as { id: string }).id);
  },
  update: async (id: string, payload: Partial<Task>): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb.from("tasks").update(payload as Record<string, unknown>).eq("id", id);
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
  remove: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb
      .from("tasks")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() })
      .eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
  complete: async (id: string): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb
      .from("tasks")
      .update({ status: "DONE", completed_at: new Date().toISOString() })
      .eq("id", id);
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
  reopen: async (id: string): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb.from("tasks").update({ status: "TODO", completed_at: null }).eq("id", id);
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
  addChecklistItem: async (id: string, title: string): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb
      .from("task_checklist_items")
      .insert({ task_id: id, title, workspace_id: getWorkspaceId(), created_by: getAppUserId() });
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
  updateChecklistItem: async (id: string, itemId: string, payload: { title?: string; is_done?: boolean }): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb.from("task_checklist_items").update(payload).eq("id", itemId);
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
  deleteChecklistItem: async (id: string, itemId: string): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb
      .from("task_checklist_items")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() })
      .eq("id", itemId);
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
};

// ─── Task 5: notesApi + financeApi CRUD ──────────────────────────────────────

import type { FinanceCategory, FinanceSummary, FinanceReport, Note, Transaction } from "@/types";

export const notesApi = {
  list: async (): Promise<Note[]> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("notes")
      .select("*")
      .eq("is_deleted", false)
      .order("updated_at", { ascending: false });
    if (error) throw toApiException(error);
    return (data ?? []) as Note[];
  },
  create: async (payload: Partial<Note>): Promise<Note> => {
    const sb = await getSupabase();
    // Stamp NOT-NULL columns that NoteCreate defaults on the backend:
    //   is_pinned: false, tags: [] — content is nullable so no stamp needed.
    const { data, error } = await sb
      .from("notes")
      .insert({
        is_pinned: false,
        tags: [],
        ...payload,
        created_by: getAppUserId(),
        workspace_id: getWorkspaceId(),
      })
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as Note;
  },
  update: async (id: string, payload: Partial<Note>): Promise<Note> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("notes")
      .update(payload as Record<string, unknown>)
      .eq("id", id)
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as Note;
  },
  remove: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb
      .from("notes")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() })
      .eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
};

// Finance transaction query params (mirrors apiRest.financeApi.listTransactions).
type TxQuery = {
  year?: number;
  month?: number;
  currency?: string;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
};

const financeCrud = {
  listCategories: async (): Promise<FinanceCategory[]> => {
    const sb = await getSupabase();
    // Backend orders by created_at DESC (finance_service.list_categories).
    const { data, error } = await sb
      .from("finance_categories")
      .select("*")
      .eq("is_deleted", false)
      .order("created_at", { ascending: false });
    if (error) throw toApiException(error);
    return (data ?? []) as FinanceCategory[];
  },
  createCategory: async (payload: { name: string; type: string }): Promise<FinanceCategory> => {
    const sb = await getSupabase();
    // name and type are required caller-supplied fields; created_by + workspace_id stamped here.
    const { data, error } = await sb
      .from("finance_categories")
      .insert({
        ...payload,
        created_by: getAppUserId(),
        workspace_id: getWorkspaceId(),
      })
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as FinanceCategory;
  },
  removeCategory: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb
      .from("finance_categories")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() })
      .eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
  listTransactions: async (params?: TxQuery): Promise<Transaction[]> => {
    const sb = await getSupabase();
    let q = sb.from("transactions").select("*").eq("is_deleted", false);
    if (params?.currency) q = q.eq("currency", params.currency.toUpperCase());
    // start/end take priority; year+month only applies when both start and end are absent
    // (mirrors backend finance_service.list_transactions logic).
    if (params?.start) {
      q = q.gte("transaction_date", params.start);
    }
    if (params?.end) {
      // Backend uses <= (inclusive), matching range_summary filter.
      q = q.lte("transaction_date", params.end);
    }
    if (!params?.start && !params?.end && params?.year && params?.month) {
      const mm = String(params.month).padStart(2, "0");
      const startDate = `${params.year}-${mm}-01`;
      // Last day via monthrange equivalent: next month minus one day, or Dec → Jan next year.
      const nextMonth = params.month === 12 ? 1 : params.month + 1;
      const nextYear = params.month === 12 ? params.year + 1 : params.year;
      const lastDayDate = new Date(nextYear, nextMonth - 1, 0);
      const lastDay = String(lastDayDate.getDate()).padStart(2, "0");
      const endDate = `${params.year}-${mm.replace(mm, String(params.month).padStart(2, "0"))}-${lastDay}`;
      q = q.gte("transaction_date", startDate).lte("transaction_date", endDate);
    }
    q = q.order("transaction_date", { ascending: false });
    if (params?.limit) q = q.limit(params.limit);
    if (params?.offset) q = q.range(params.offset, params.offset + (params.limit ?? 100) - 1);
    const { data, error } = await q;
    if (error) throw toApiException(error);
    return (data ?? []) as Transaction[];
  },
  createTransaction: async (payload: Record<string, unknown>): Promise<Transaction> => {
    const sb = await getSupabase();
    // currency defaults to "IDR" on the backend (DEFAULT_CURRENCY); stamp it so the
    // NOT-NULL constraint is satisfied when the caller omits it.
    // type, amount, transaction_date are required caller-supplied fields.
    const { data, error } = await sb
      .from("transactions")
      .insert({
        currency: "IDR",
        ...payload,
        created_by: getAppUserId(),
        workspace_id: getWorkspaceId(),
      })
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as Transaction;
  },
  updateTransaction: async (id: string, payload: Record<string, unknown>): Promise<Transaction> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("transactions")
      .update(payload)
      .eq("id", id)
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as Transaction;
  },
  removeTransaction: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb
      .from("transactions")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() })
      .eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
};

// ─── Task 6: financeApi.summary + report (client-side aggregation) ─────────

// Reproduces backend finance_service.range_summary:
//   total_income = sum(amount for t if t.type == "INCOME")
//   total_expense = sum(amount for t if t.type == "EXPENSE")
//   balance = total_income - total_expense
//   transaction_count = len(transactions)
// float() applied to amounts; no rounding beyond JS floating-point arithmetic.
function aggregateSummary(txns: Transaction[], currency: string): {
  total_income: number;
  total_expense: number;
  balance: number;
  transaction_count: number;
  currency: string;
} {
  let total_income = 0;
  let total_expense = 0;
  for (const t of txns) {
    const amt = Number(t.amount) || 0;
    if (t.type === "INCOME") {
      total_income += amt;
    } else {
      total_expense += amt;
    }
  }
  return {
    total_income,
    total_expense,
    balance: total_income - total_expense,
    transaction_count: txns.length,
    currency,
  };
}

export const financeApi = {
  ...financeCrud,

  // Returns FinanceSummary: { year, month, currency, total_income, total_expense,
  //   balance, transaction_count }
  // Matches backend monthly_summary which calls range_summary with
  //   start = date(year, month, 1), end = date(year, month, last_day).
  summary: async (year: number, month: number, currency = "IDR"): Promise<FinanceSummary> => {
    const txns = await financeCrud.listTransactions({ year, month, currency });
    const agg = aggregateSummary(txns, currency);
    return {
      year,
      month,
      currency: agg.currency,
      total_income: agg.total_income,
      total_expense: agg.total_expense,
      balance: agg.balance,
      transaction_count: agg.transaction_count,
    };
  },

  // Returns FinanceReport: { period_type, start_date, end_date, currency,
  //   total_income, total_expense, balance, transaction_count }
  // Matches backend range_summary. The backend uses inclusive start and end dates
  // (transaction_date >= start AND transaction_date <= end).
  report: async (payload: {
    start: string;
    end: string;
    periodType?: string;
    currency?: string;
  }): Promise<FinanceReport> => {
    const currency = payload.currency ?? "IDR";
    const txns = await financeCrud.listTransactions({
      start: payload.start,
      end: payload.end,
      currency,
    });
    const agg = aggregateSummary(txns, currency);
    return {
      period_type: payload.periodType ?? "custom",
      start_date: payload.start,
      end_date: payload.end,
      currency: agg.currency,
      total_income: agg.total_income,
      total_expense: agg.total_expense,
      balance: agg.balance,
      transaction_count: agg.transaction_count,
    };
  },
};
