// frontend/lib/apiSupabase.ts — Supabase-backed seam. Groups are replaced with real
// Supabase impls task-by-task in later pairs; until then they passthrough to REST.
//
// Compute/file groups (ai/memory/knowledge/drive/system/n8n/google/settings) are NOT
// ported in 3.7 — re-export the REST impl (they are hidden on mobile UI).
export {
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

// The `id` PK has NO server-side default in Postgres — the SQLAlchemy models mint
// UUIDs Python-side, so the DDL emits none. Desktop inserts via SQLAlchemy get an
// id; mobile inserts via supabase-js do NOT, and fail with "null value in column
// id violates not-null constraint". So mint the id on the client for every new row.
function newId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  // Fallback for older WebViews without crypto.randomUUID.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0;
    return (ch === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// Fields every new row needs: a fresh id + the workspace scope. Until the post-login
// bootstrap (loadMe) sets the workspace + app user, an insert would send nulls and
// fail RLS/NOT NULL — surface a clear, actionable error instead.
function newRow(): { id: string; workspace_id: string; created_by: string } {
  const workspace_id = getWorkspaceId();
  const created_by = getAppUserId();
  if (!workspace_id || !created_by) {
    throw new ApiException("You're not signed in. Please sign in again.", "NOT_AUTHENTICATED", 401);
  }
  return { id: newId(), workspace_id, created_by };
}

async function loadMe(): Promise<Me> {
  const sb = await getSupabase();
  const { data: auth, error: ae } = await sb.auth.getUser();
  if (ae || !auth?.user) throw toApiException(ae ?? { status: 401, message: "Not authenticated" }, 401);
  // RLS returns only this user's profile (profiles.id = app_user_id()). Use
  // maybeSingle: if the account isn't linked yet (profiles.supabase_user_id null)
  // RLS returns 0 rows, and .single() would throw an opaque PGRST116 that breaks
  // login entirely. Surface a clear, actionable error instead.
  const { data: profile, error: pe } = await sb.from("profiles").select("*").maybeSingle();
  if (pe) throw toApiException(pe);
  if (!profile) {
    // Self-provisioning (provision_me on sign-in) normally prevents this. If it
    // still happens, the RPC isn't deployed yet — keep it actionable, not desktop-bound.
    throw new ApiException(
      "We’re still finishing your account setup. Please try signing in again in a moment.",
      "PROFILE_NOT_INITIALIZED",
      409,
    );
  }
  setAppUserId(profile.id);
  // Resolve the user's OWNED workspace (matches backend auth_service.get_default_workspace).
  // RLS policy p_owner restricts workspaces to rows where owner_id = app_user_id().
  const { data: ws, error: we } = await sb
    .from("workspaces").select("*")
    .order("created_at", { ascending: true }).limit(1).maybeSingle();
  if (we) throw toApiException(we);
  if (!ws) {
    throw new ApiException(
      "We’re still finishing your workspace setup. Please try signing in again in a moment.",
      "WORKSPACE_NOT_INITIALIZED",
      409,
    );
  }
  setWorkspaceId((ws as { id: string }).id);
  const user: User = {
    id: profile.id,
    email: auth.user.email ?? (profile as any).email ?? "",
    full_name: profile.full_name ?? null,
    created_at: profile.created_at,
  };
  return { user, workspace: ws as Workspace };
}

async function supabaseSignIn(email: string, password: string): Promise<AuthToken> {
  const sb = await getSupabase();
  const { data, error } = await sb.auth.signInWithPassword({ email, password });
  if (error) throw toApiException(error, 401);
  // Best-effort self-provision (idempotent): covers first login after email
  // confirmation and repairs unlinked/legacy accounts. Swallowed if the RPC isn't
  // deployed yet — loadMe() stays the source of truth for whether the account works.
  await sb.rpc("provision_me", { p_full_name: null }).then(() => {}, () => {});
  const meResult = await loadMe();
  return {
    access_token: data.session?.access_token ?? "",
    token_type: "bearer",
    user: meResult.user,
  };
}

export const authApi = {
  // Mobile registration runs entirely against Supabase — no backend required (a phone
  // can't reach the local backend). Flow: signUp → signIn (get an authed session) →
  // provision_me() RPC (SECURITY DEFINER: creates profile + workspace + owner membership,
  // bypassing the RLS chicken-and-egg) → loadMe(). Idempotent if the account already
  // exists (e.g. created on desktop first): provision_me adopts/links it.
  register: async (email: string, password: string, fullName?: string): Promise<AuthToken> => {
    const sb = await getSupabase();
    const { error: signUpErr } = await sb.auth.signUp({
      email,
      password,
      // Stash the name on the auth user so provisioning can recover it even when
      // the profile is created on a later (post-confirmation) login.
      options: fullName ? { data: { full_name: fullName } } : undefined,
    });
    // "already registered" is fine — fall through to sign-in + provision.
    if (signUpErr && !/already\s*(registered|exists|in use)/i.test(signUpErr.message)) {
      throw toApiException(signUpErr);
    }
    const { data: signIn, error: signInErr } = await sb.auth.signInWithPassword({ email, password });
    if (signInErr) {
      // Most common standalone cause: project requires email confirmation, so no
      // session is issued until the link is clicked. Make that actionable.
      const hint = /confirm/i.test(signInErr.message)
        ? " — confirm your email, or disable email confirmation in Supabase → Authentication → Providers → Email."
        : "";
      throw toApiException({ ...signInErr, message: signInErr.message + hint }, 401);
    }
    const { error: provErr } = await sb.rpc("provision_me", { p_full_name: fullName ?? null });
    if (provErr) {
      // Never show the raw PostgREST/schema-cache text to users; log it for devs.
      console.error("provision_me failed:", provErr);
      const notDeployed =
        provErr.code === "PGRST202" ||
        /schema cache|could not find the function|provision_me/i.test(provErr.message ?? "");
      throw new ApiException(
        notDeployed
          ? "We couldn’t finish setting up your account. Please try again in a moment."
          : provErr.message || "We couldn’t finish setting up your account.",
        "PROVISION_FAILED",
        502,
      );
    }
    const me = await loadMe();
    return {
      access_token: signIn.session?.access_token ?? "",
      token_type: "bearer",
      user: me.user,
    };
  },
  login: (email: string, password: string): Promise<AuthToken> => supabaseSignIn(email, password),
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
    // `checklist` is a list of step titles, NOT a column on `tasks` — spreading it
    // into the insert caused "Could not find the 'checklist' column of 'tasks'".
    // Create the task, then add normalized task_checklist_items (mirrors backend
    // task_service.create_task, capped at 5).
    const { checklist, ...taskFields } = payload;
    const { data, error } = await sb
      .from("tasks")
      .insert({ status: "TODO", priority: "NORMAL", ...taskFields, ...newRow() })
      .select("id")
      .single();
    if (error) throw toApiException(error);
    const taskId = (data as { id: string }).id;
    const titles = Array.isArray(checklist)
      ? (checklist as unknown[]).map((t) => String(t).trim()).filter(Boolean).slice(0, 5)
      : [];
    if (titles.length) {
      const rows = titles.map((title, position) => ({ task_id: taskId, title, position, ...newRow() }));
      const { error: ciErr } = await sb.from("task_checklist_items").insert(rows);
      if (ciErr) throw toApiException(ciErr);
    }
    return fetchTask(taskId);
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
    // Compute next position to match desktop formula (task_service.py add_checklist_item):
    //   position = max(i.position for i in active_items, default=-1) + 1
    // Base case (no active items): max(default=-1) + 1 = 0 → first item at position 0.
    const current = await fetchTask(id);
    const positions = (current.checklist_items ?? []).map((c) => c.position);
    const nextPosition = positions.length ? Math.max(...positions) + 1 : 0;
    const { error } = await sb
      .from("task_checklist_items")
      .insert({ task_id: id, title, position: nextPosition, ...newRow() });
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
      .order("is_pinned", { ascending: false })
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
        ...newRow(),
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
        ...newRow(),
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
      const endDate = `${params.year}-${mm}-${lastDay}`;
      q = q.gte("transaction_date", startDate).lte("transaction_date", endDate);
    }
    q = q.order("transaction_date", { ascending: false }).order("created_at", { ascending: false });
    // range() already encodes offset+limit; use it for pagination, else plain
    // limit(). Combining both double-applies the bound and drops rows.
    if (params?.offset) {
      q = q.range(params.offset, params.offset + (params.limit ?? 100) - 1);
    } else if (params?.limit) {
      q = q.limit(params.limit);
    }
    const { data, error } = await q;
    if (error) throw toApiException(error);
    return (data ?? []) as Transaction[];
  },
  createTransaction: async (payload: Record<string, unknown>): Promise<Transaction> => {
    const sb = await getSupabase();
    // currency defaults to "IDR" on the backend (DEFAULT_CURRENCY); stamp it so the
    // NOT-NULL constraint is satisfied when the caller omits it.
    // Normalize to uppercase and trim to 3 chars to match backend `.upper()[:3]`.
    // type, amount, transaction_date are required caller-supplied fields.
    const currency = ((payload.currency as string | undefined) ?? "IDR").toUpperCase().slice(0, 3);
    // Resolve category_name_snapshot at write time so the label survives category deletion.
    let category_name_snapshot: string | null = null;
    if (payload.category_id != null) {
      const cats = await financeCrud.listCategories();
      category_name_snapshot = cats.find((c) => c.id === payload.category_id)?.name ?? null;
    }
    const { data, error } = await sb
      .from("transactions")
      .insert({
        ...payload,
        currency,
        category_name_snapshot,
        ...newRow(),
      })
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as Transaction;
  },
  updateTransaction: async (id: string, payload: Record<string, unknown>): Promise<Transaction> => {
    const sb = await getSupabase();
    // Mirror backend: only touch category_name_snapshot when category_id is present in payload.
    // If category_id is explicitly null, set snapshot to null; otherwise resolve from categories.
    const extra: Record<string, unknown> = {};
    if ("category_id" in payload) {
      if (payload.category_id == null) {
        extra.category_name_snapshot = null;
      } else {
        const cats = await financeCrud.listCategories();
        extra.category_name_snapshot = cats.find((c) => c.id === payload.category_id)?.name ?? null;
      }
    }
    const { data, error } = await sb
      .from("transactions")
      .update({ ...payload, ...extra })
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
    } else if (t.type === "EXPENSE") {
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
    const normalizedCurrency = currency.toUpperCase().slice(0, 3);
    const txns = await financeCrud.listTransactions({ year, month, currency: normalizedCurrency });
    const agg = aggregateSummary(txns, normalizedCurrency);
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
    const currency = (payload.currency ?? "IDR").toUpperCase().slice(0, 3);
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

// ─── Task 7: calendarApi + routinesApi (both backed by calendar_events) ───────
//
// NOT NULL columns in calendar_events with no server default (must be stamped):
//   workspace_id      → getWorkspaceId()
//   created_by        → getAppUserId()
//   title             → required caller-supplied field
//   start_at          → required caller-supplied field
//   all_day           → Boolean, default=False in ORM / CalendarEventCreate default=False
//   repeat_rule       → String(16), default="once" in ORM / CalendarEventCreate default="once"
//   is_deleted        → Boolean, default=False in ORM — Postgres has column default; stamp anyway
//
// calendar_events HAS is_deleted → list filters is_deleted=false; remove is soft-delete.

import type { CalendarEvent, RoutineGenerateResult, RoutineSyncInfo } from "@/types";

async function calList(): Promise<CalendarEvent[]> {
  const sb = await getSupabase();
  const { data, error } = await sb
    .from("calendar_events")
    .select("*")
    .eq("is_deleted", false)
    .order("start_at", { ascending: true });
  if (error) throw toApiException(error);
  return (data ?? []) as CalendarEvent[];
}

async function calCreate(payload: Record<string, unknown>): Promise<CalendarEvent> {
  const sb = await getSupabase();
  const { data, error } = await sb
    .from("calendar_events")
    .insert({
      // Defaults for NOT NULL columns without server default (ORM/schema defaults):
      all_day: false,
      repeat_rule: "once",
      is_deleted: false,
      // Caller payload wins over the above defaults:
      ...payload,
      // Stamp tenancy columns last so callers cannot override them:
      ...newRow(),
    })
    .select("*")
    .single();
  if (error) throw toApiException(error);
  return data as CalendarEvent;
}

async function calUpdate(id: string, payload: Record<string, unknown>): Promise<CalendarEvent> {
  const sb = await getSupabase();
  const { data, error } = await sb
    .from("calendar_events")
    .update(payload)
    .eq("id", id)
    .select("*")
    .single();
  if (error) throw toApiException(error);
  return data as CalendarEvent;
}

async function calRemove(id: string): Promise<{ id: string }> {
  const sb = await getSupabase();
  const { error } = await sb
    .from("calendar_events")
    .update({ is_deleted: true, deleted_at: new Date().toISOString() })
    .eq("id", id);
  if (error) throw toApiException(error);
  return { id };
}

export const calendarApi = {
  list: calList,
  create: calCreate,
  update: calUpdate,
  remove: calRemove,
};

export const routinesApi = {
  list: (params?: { start?: string; end?: string }): Promise<CalendarEvent[]> => {
    // On Supabase the routines table doesn't exist separately — we query calendar_events
    // directly (the REST 404-fallback target IS this table).
    // start/end date filtering is applied when provided.
    return (async () => {
      const sb = await getSupabase();
      let q = sb
        .from("calendar_events")
        .select("*")
        .eq("is_deleted", false);
      if (params?.start) q = q.gte("start_at", params.start);
      if (params?.end) q = q.lte("start_at", params.end);
      q = q.order("start_at", { ascending: true });
      const { data, error } = await q;
      if (error) throw toApiException(error);
      return (data ?? []) as CalendarEvent[];
    })();
  },
  create: calCreate,
  update: calUpdate,
  remove: calRemove,
  createBatch: async (items: Record<string, unknown>[]): Promise<CalendarEvent[]> => {
    const sb = await getSupabase();
    const rows = items.map((e) => ({
      all_day: false,
      repeat_rule: "once",
      is_deleted: false,
      ...e,
      ...newRow(),
    }));
    const { data, error } = await sb.from("calendar_events").insert(rows).select("*");
    if (error) throw toApiException(error);
    return (data ?? []) as CalendarEvent[];
  },
  // AI generation requires the backend secret — unavailable in the mobile Supabase-direct mode.
  generate: async (_payload: {
    prompt: string;
    date: string;
    period: string;
    use_context?: boolean;
  }): Promise<RoutineGenerateResult> => {
    throw new ApiException(
      "Routine generation runs on the desktop app",
      "UNAVAILABLE_ON_MOBILE",
      501,
      null,
    );
  },
  // In Supabase mode we ARE syncing directly — report as active.
  syncStatus: async (): Promise<RoutineSyncInfo> => ({
    status: "active",
    configured: true,
  }),
};

// ─── Task 8: automationsApi + weatherApi ─────────────────────────────────────
//
// NOT NULL columns in automations with no server default (must be stamped):
//   workspace_id   → getWorkspaceId()
//   created_by     → getAppUserId()
//   name           → required caller-supplied field
//   trigger_type   → String, default="manual" in ORM / AutomationCreate default="manual"
//   action_type    → String, default="noop" in ORM / AutomationCreate default="noop"
//   config         → JSONType, default=dict in ORM / AutomationCreate default_factory=dict
//   enabled        → Boolean, default=False in ORM — NOT in AutomationCreate (caller cannot set at create)
//   is_deleted     → Boolean, default=False in ORM — Postgres column default; stamp defensively
//
// automations HAS is_deleted → list filters is_deleted=false; remove is soft-delete.
//
// NOT NULL columns in weather_locations with no server default (must be stamped):
//   workspace_id → getWorkspaceId()
//   created_by   → getAppUserId()
//   name         → required caller-supplied field
//   is_default   → Boolean, default=False in ORM / WeatherLocationCreate default=False
//
// weather_locations has NO is_deleted column → list has NO is_deleted filter;
// removeLocation is a HARD DELETE.

import type { Automation, WeatherLocation, WeatherCurrent } from "@/types";

export const automationsApi = {
  list: async (): Promise<Automation[]> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("automations")
      .select("*")
      .eq("is_deleted", false)
      .order("created_at", { ascending: false });
    if (error) throw toApiException(error);
    return (data ?? []) as Automation[];
  },
  create: async (payload: Record<string, unknown>): Promise<Automation> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("automations")
      .insert({
        // Defaults for NOT NULL columns (ORM/schema defaults stamped before payload):
        trigger_type: "manual",
        action_type: "noop",
        config: {},
        enabled: false,
        is_deleted: false,
        // Caller payload wins:
        ...payload,
        // Tenancy columns last — cannot be overridden:
        ...newRow(),
      })
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as Automation;
  },
  update: async (id: string, payload: Record<string, unknown>): Promise<Automation> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("automations")
      .update(payload)
      .eq("id", id)
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as Automation;
  },
  remove: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb
      .from("automations")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() })
      .eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
};

export const weatherApi = {
  listLocations: async (): Promise<WeatherLocation[]> => {
    const sb = await getSupabase();
    // weather_locations has NO is_deleted column — no filter applied.
    const { data, error } = await sb
      .from("weather_locations")
      .select("*")
      .order("created_at", { ascending: true });
    if (error) throw toApiException(error);
    return (data ?? []) as WeatherLocation[];
  },
  addLocation: async (name: string, isDefault = false): Promise<WeatherLocation> => {
    const sb = await getSupabase();
    const { data, error } = await sb
      .from("weather_locations")
      .insert({
        // Defaults before payload so caller can override is_default:
        is_default: isDefault,
        // Required caller-supplied field:
        name,
        // Tenancy columns last:
        ...newRow(),
      })
      .select("*")
      .single();
    if (error) throw toApiException(error);
    return data as WeatherLocation;
  },
  // Hard delete — weather_locations has no is_deleted column.
  removeLocation: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb.from("weather_locations").delete().eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
  // Live weather requires a backend API secret — unavailable in mobile Supabase-direct mode.
  current: async (_location?: string): Promise<WeatherCurrent> => {
    throw new ApiException(
      "Live weather runs on the desktop app",
      "UNAVAILABLE_ON_MOBILE",
      501,
      null,
    );
  },
};
