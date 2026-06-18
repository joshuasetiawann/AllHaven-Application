# Mobile-on-Supabase Data Layer (Plan 3 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second data implementation behind the existing `frontend/lib/api.ts` seam that talks **directly to Supabase** (`supabase-js`, RLS-scoped) for the v3.7 CRUD feature set, selected at build time by `NEXT_PUBLIC_DATA_MODE=supabase`, so the mobile APK works with no AllHaven backend in the path.

**Architecture:** `api.ts` becomes a thin selector: when `DATA_MODE === "supabase"` it re-exports the `*Api` objects from a new `frontend/lib/apiSupabase.ts`; otherwise it keeps today's REST impl. The Supabase impl returns the **identical unwrapped entity shapes** (`@/types`) and throws **`ApiException`-compatible** errors (`message, code, statusCode, details`) so every existing call site, the `routinesApi` 404-fallback, and `handleUnauthorized` keep working unchanged. The whole stack is snake_case end-to-end, so PostgREST rows map 1:1 to the frontend types with **no case translation**. `supabase-js` is lazy-imported so it never enters the desktop/web bundle.

**Tech Stack:** Next.js 14 (static export for mobile), TypeScript 5.5, `@supabase/supabase-js` (new, pinned), `@capacitor/preferences` (existing) for session storage. No new test runner — gates are `npx tsc --noEmit` + `npm run build` / `npm run build:mobile`.

## Global Constraints

- **Same seam, zero page/component changes.** Pages import the `*Api` objects from `@/lib/api`; that import must keep working. Only `api.ts` chooses the impl. (Audit confirmed: zero `fetch()` calls outside `api.ts`.)
- **Contract preservation:** every Supabase method returns the same unwrapped entity type as the REST method (e.g. `tasksApi.list()` → `Task[]`, not `{data: Task[]}`), and on failure throws `new ApiException(message, code, statusCode, details)`. Map PostgREST/Auth errors: 401 → statusCode 401 (so `handleUnauthorized` fires), 403/PGRST → preserve `code`, missing table/route → statusCode 404 (so `routinesApi` fallback triggers).
- **snake_case everywhere, no mapping.** Table + column names match the backend exactly (`tasks`, `task_checklist_items`, `notes`, `transactions`, `finance_categories`, `calendar_events`, `weather_locations`, `automations`, `profiles`, `workspaces`, `workspace_members`). Entity field names in `@/types` already equal the DB columns.
- **Soft-delete:** `list` reads must filter `is_deleted = false` on tables that have it (`tasks`, `task_checklist_items`, `notes`, `transactions`, `finance_categories`, `calendar_events`, `automations`). `remove` is a soft delete: `update {is_deleted:true, deleted_at: <ISO now>}` — NOT a hard `delete`. (`weather_locations`, `workspaces`, `workspace_members` hard-delete.)
- **Scoping/inserts:** the client sets `workspace_id` (and `created_by` where the column exists) on insert; RLS (migration 0013) enforces tenancy via `app_user_id()` → `profiles.supabase_user_id`. The current `workspace_id` is resolved once at login (`me()` bootstrap) and cached in-module.
- **Secrets:** only `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` reach the bundle (publishable anon key only — never `service_role`). `NEXT_PUBLIC_*` is the only channel into the static export.
- **Lazy import:** `@supabase/supabase-js` is loaded via `await import(...)` so it stays out of the desktop bundle (mirror of the `@capacitor/preferences` precedent).
- **Build from `frontend/`:** typecheck `cd frontend && npx tsc --noEmit`; web build `npm run build`; mobile build `npm run build:mobile`.
- **Out of scope (3.8/3.9 via Edge Functions):** `aiApi`, `memoryApi`, `knowledgeApi`, `driveApi` (multipart), `systemApi`, `n8nApi`, `googleApi`, and `weatherApi.current` (live provider via backend secret). On mobile these are hidden/disabled, not ported.

---

## File structure

- **Create** `frontend/lib/supabaseClient.ts` — lazy `supabase-js` singleton + `DATA_MODE`, session storage adapter, cached `currentWorkspaceId`.
- **Create** `frontend/lib/supabaseError.ts` — `toApiException(error)` mapper (PostgREST/Auth → `ApiException`).
- **Create** `frontend/lib/apiSupabase.ts` — the `*Api` objects backed by Supabase (in-scope groups only).
- **Modify** `frontend/lib/api.ts` — `DATA_MODE` selector that re-exports REST or Supabase impl.
- **Modify** `frontend/components/layout/AppShell.tsx` — restore the Supabase session before the first query in mobile/Supabase mode.
- **Modify** `frontend/package.json` — add pinned `@supabase/supabase-js`; extend `build:mobile` env.
- **Modify** `.github/workflows/android-apk.yml` — bake `NEXT_PUBLIC_DATA_MODE` + Supabase url/anon key.

---

## Task 1: Dependency + Supabase client singleton

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/lib/supabaseClient.ts`

**Interfaces:**
- Produces:
  - `DATA_MODE: boolean` (`process.env.NEXT_PUBLIC_DATA_MODE === "supabase"`).
  - `getSupabase(): Promise<SupabaseClient>` — lazy singleton.
  - `getWorkspaceId(): string | null` / `setWorkspaceId(id: string|null)` — in-module cache of the active workspace.

- [ ] **Step 1: Add the pinned dependency**

```bash
cd frontend && npm install @supabase/supabase-js@2.45.4 --save-exact
```
Confirm `package.json` now has `"@supabase/supabase-js": "2.45.4"` (exact, no caret) and `package-lock.json` is updated. Commit the lockfile.

- [ ] **Step 2: Create the client singleton**

```ts
// frontend/lib/supabaseClient.ts
import type { SupabaseClient } from "@supabase/supabase-js";

export const DATA_MODE = process.env.NEXT_PUBLIC_DATA_MODE === "supabase";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

let client: SupabaseClient | null = null;
let workspaceId: string | null = null;

// Async storage backed by Capacitor Preferences so the session survives app restarts.
const capacitorStorage = {
  getItem: async (key: string) => {
    const { Preferences } = await import("@capacitor/preferences");
    return (await Preferences.get({ key })).value;
  },
  setItem: async (key: string, value: string) => {
    const { Preferences } = await import("@capacitor/preferences");
    await Preferences.set({ key, value });
  },
  removeItem: async (key: string) => {
    const { Preferences } = await import("@capacitor/preferences");
    await Preferences.remove({ key });
  },
};

export async function getSupabase(): Promise<SupabaseClient> {
  if (client) return client;
  const { createClient } = await import("@supabase/supabase-js");
  client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      storage: capacitorStorage,
      storageKey: "allhaven_supabase_session",
    },
  });
  return client;
}

export function getWorkspaceId(): string | null {
  return workspaceId;
}
export function setWorkspaceId(id: string | null): void {
  workspaceId = id;
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (types for `@supabase/supabase-js` resolve).

---

## Task 2: `DATA_MODE` seam + PostgREST→ApiException mapper

**Files:**
- Create: `frontend/lib/supabaseError.ts`
- Create: `frontend/lib/apiSupabase.ts` (scaffold)
- Modify: `frontend/lib/api.ts`

**Interfaces:**
- Consumes: `DATA_MODE`, `ApiException`.
- Produces:
  - `toApiException(error: unknown, fallbackStatus?: number): ApiException`.
  - `apiSupabase` module exporting the same names as `api.ts` (`authApi, tasksApi, notesApi, financeApi, calendarApi, routinesApi, weatherApi, automationsApi, settingsApi`), initially only the ones implemented in later tasks; unimplemented compute APIs (`aiApi`, etc.) re-export the REST impl so nothing breaks.

- [ ] **Step 1: Error mapper**

```ts
// frontend/lib/supabaseError.ts
import { ApiException } from "@/lib/api";

// PostgrestError: { message, details, hint, code }. AuthError: { message, status }.
export function toApiException(error: unknown, fallbackStatus = 400): ApiException {
  const e = error as { message?: string; code?: string; status?: number; details?: unknown };
  const message = e?.message || "Supabase request failed";
  const code = e?.code || "SUPABASE_ERROR";
  let statusCode = typeof e?.status === "number" ? e.status : fallbackStatus;
  // PostgREST RLS / auth failures surface as 401/403 so handleUnauthorized + fallbacks fire correctly.
  if (code === "PGRST301" || code === "42501") statusCode = 403;
  if (e?.status === 401) statusCode = 401;
  if (code === "PGRST116") statusCode = 404; // no rows / missing
  return new ApiException(message, code, statusCode, e?.details ?? error);
}
```

- [ ] **Step 2: apiSupabase scaffold (re-export REST for not-yet-ported groups)**

```ts
// frontend/lib/apiSupabase.ts
// Supabase-backed implementations of the *Api seam. Populated task-by-task.
// Compute/file groups (ai/memory/knowledge/drive/system/n8n/google) are NOT ported in 3.7;
// re-export the REST impl so imports keep resolving (they are hidden on mobile UI).
export {
  aiApi, memoryApi, knowledgeApi, driveApi, systemApi, n8nApi, googleApi, settingsApi,
} from "@/lib/apiRest";

// The ported groups are added below in later tasks:
// export const authApi = ... (Task 3)
// export const tasksApi = ... (Task 4)
// export const notesApi, financeApi = ... (Tasks 5–6)
// export const calendarApi, routinesApi = ... (Task 7)
// export const automationsApi, weatherApi = ... (Task 8)
```

- [ ] **Step 3: Split today's impl into `apiRest.ts` and make `api.ts` the selector**

Rename the current implementation file so both impls can coexist:
1. `git mv frontend/lib/api.ts frontend/lib/apiRest.ts`
2. In `apiRest.ts`, keep ALL existing exports (`ApiException`, `API_BASE_URL`, every `*Api`, interfaces).
3. Create a new `frontend/lib/api.ts` selector:

```ts
// frontend/lib/api.ts — selects the data implementation at build time.
import { DATA_MODE } from "@/lib/supabaseClient";

export { ApiException, API_BASE_URL } from "@/lib/apiRest";
export type { AiPolicy, ProposalApproval } from "@/lib/apiRest";

import * as rest from "@/lib/apiRest";
import * as supa from "@/lib/apiSupabase";

const impl = DATA_MODE ? supa : rest;

export const authApi = impl.authApi;
export const tasksApi = impl.tasksApi;
export const notesApi = impl.notesApi;
export const financeApi = impl.financeApi;
export const calendarApi = impl.calendarApi;
export const routinesApi = impl.routinesApi;
export const weatherApi = impl.weatherApi;
export const automationsApi = impl.automationsApi;
// compute/file groups always come from REST (hidden on mobile)
export const aiApi = rest.aiApi;
export const memoryApi = rest.memoryApi;
export const knowledgeApi = rest.knowledgeApi;
export const driveApi = rest.driveApi;
export const systemApi = rest.systemApi;
export const n8nApi = rest.n8nApi;
export const googleApi = rest.googleApi;
export const settingsApi = rest.settingsApi;
```

> **Note:** `ApiException` must be defined in `apiRest.ts` and imported by `supabaseError.ts`/`apiSupabase.ts` from `@/lib/api` (which re-exports it) — avoid a circular import by importing `ApiException` from `@/lib/apiRest` inside `apiSupabase.ts` if the selector causes a cycle.

- [ ] **Step 4: Typecheck + web build (REST path unchanged)**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: builds clean; web still uses REST (`DATA_MODE` false).

- [ ] **Step 5: Commit (Tasks 1–2)**

```bash
git add frontend/package.json frontend/package-lock.json frontend/lib/supabaseClient.ts \
        frontend/lib/supabaseError.ts frontend/lib/apiSupabase.ts frontend/lib/apiRest.ts frontend/lib/api.ts
git commit -m "feat(mobile): supabase-js client + DATA_MODE seam + error mapper"
```

---

## Task 3: `authApi` on Supabase Auth + `me()` workspace bootstrap

**Files:**
- Modify: `frontend/lib/apiSupabase.ts`

**Interfaces:**
- Consumes: `getSupabase`, `setWorkspaceId`, `toApiException`, types `AuthToken`, `Me`, `User`, `Workspace`.
- Produces: `authApi` with `login`, `register`, `logout`, `me`, `updateMe` returning the same shapes as REST. `me()` caches the active `workspace_id`.

- [ ] **Step 1: Implement `authApi`**

```ts
// add to frontend/lib/apiSupabase.ts
import type { AuthToken, Me, User, Workspace } from "@/types";
import { ApiException } from "@/lib/apiRest";
import { getSupabase, setWorkspaceId } from "@/lib/supabaseClient";
import { toApiException } from "@/lib/supabaseError";

async function loadMe(): Promise<Me> {
  const sb = await getSupabase();
  const { data: auth, error: ae } = await sb.auth.getUser();
  if (ae || !auth?.user) throw toApiException(ae ?? { status: 401, message: "Not authenticated" }, 401);
  // RLS returns only this user's profile (profiles.id = app_user_id()).
  const { data: profile, error: pe } = await sb.from("profiles").select("*").single();
  if (pe) throw toApiException(pe);
  // RLS returns only this user's membership; join the workspace row.
  const { data: member, error: me } = await sb
    .from("workspace_members").select("workspace_id, workspaces(*)").limit(1).single();
  if (me) throw toApiException(me);
  const ws = (member as any).workspaces as Workspace;
  setWorkspaceId(ws.id);
  const user: User = {
    id: profile.id, email: auth.user.email ?? profile.email ?? "",
    full_name: profile.full_name ?? null, created_at: profile.created_at,
  };
  return { user, workspace: ws };
}

export const authApi = {
  register: async (email: string, password: string, full_name?: string): Promise<AuthToken> => {
    const sb = await getSupabase();
    const { data, error } = await sb.auth.signUp({ email, password, options: { data: { full_name } } });
    if (error) throw toApiException(error);
    const me = await loadMe().catch(() => null);
    return { access_token: data.session?.access_token ?? "", token_type: "bearer", user: me?.user ?? {
      id: data.user?.id ?? "", email, full_name: full_name ?? null, created_at: new Date().toISOString() } };
  },
  login: async (email: string, password: string): Promise<AuthToken> => {
    const sb = await getSupabase();
    const { data, error } = await sb.auth.signInWithPassword({ email, password });
    if (error) throw toApiException(error, 401);
    const me = await loadMe();
    return { access_token: data.session?.access_token ?? "", token_type: "bearer", user: me.user };
  },
  logout: async (): Promise<{ logged_out: boolean }> => {
    const sb = await getSupabase();
    await sb.auth.signOut();
    setWorkspaceId(null);
    return { logged_out: true };
  },
  me: (): Promise<Me> => loadMe(),
  updateMe: async (payload: { full_name?: string; workspace_name?: string }): Promise<Me> => {
    const sb = await getSupabase();
    const me = await loadMe();
    if (payload.full_name !== undefined) {
      const { error } = await sb.from("profiles").update({ full_name: payload.full_name }).eq("id", me.user.id);
      if (error) throw toApiException(error);
    }
    if (payload.workspace_name !== undefined) {
      const { error } = await sb.from("workspaces").update({ name: payload.workspace_name }).eq("id", me.workspace.id);
      if (error) throw toApiException(error);
    }
    return loadMe();
  },
};
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean. (`apiSupabase.ts` no longer re-exports `settingsApi` from the compute line if it now defines `authApi`; keep the compute re-export line for the still-REST groups.)

---

## Task 4: `tasksApi` (incl. full-Task rebuild for complete/reopen/checklist)

**Files:**
- Modify: `frontend/lib/apiSupabase.ts`

**Interfaces:**
- Consumes: `getSupabase`, `getWorkspaceId`, `toApiException`, types `Task`.
- Produces: `tasksApi` with `list, create, update, remove, complete, reopen, addChecklistItem, updateChecklistItem, deleteChecklistItem` — each returning `Task` (or `{id}` for `remove`) with embedded `checklist_items`.

- [ ] **Step 1: Implement `tasksApi`**

```ts
// add to frontend/lib/apiSupabase.ts
import type { Task } from "@/types";
import { getWorkspaceId } from "@/lib/supabaseClient";

const TASK_SELECT = "*, checklist_items:task_checklist_items(*)";

async function fetchTask(id: string): Promise<Task> {
  const sb = await getSupabase();
  const { data, error } = await sb.from("tasks").select(TASK_SELECT).eq("id", id).single();
  if (error) throw toApiException(error);
  return data as Task;
}

export const tasksApi = {
  list: async (): Promise<Task[]> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("tasks").select(TASK_SELECT)
      .eq("is_deleted", false).order("created_at", { ascending: false });
    if (error) throw toApiException(error);
    return (data ?? []) as Task[];
  },
  create: async (payload: Record<string, unknown>): Promise<Task> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("tasks")
      .insert({ ...payload, workspace_id: getWorkspaceId() }).select("id").single();
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
    const { error } = await sb.from("tasks")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() }).eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
  complete: async (id: string): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb.from("tasks")
      .update({ status: "DONE", completed_at: new Date().toISOString() }).eq("id", id);
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
    const { error } = await sb.from("task_checklist_items")
      .insert({ task_id: id, title, workspace_id: getWorkspaceId() });
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
  updateChecklistItem: async (id: string, itemId: string,
      payload: { title?: string; is_done?: boolean }): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb.from("task_checklist_items").update(payload).eq("id", itemId);
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
  deleteChecklistItem: async (id: string, itemId: string): Promise<Task> => {
    const sb = await getSupabase();
    const { error } = await sb.from("task_checklist_items")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() }).eq("id", itemId);
    if (error) throw toApiException(error);
    return fetchTask(id);
  },
};
```

> **Note:** the `TASK_SELECT` embed pulls checklist items including soft-deleted ones. If the REST `Task.checklist_items` excludes deleted items, filter client-side in `fetchTask` (`data.checklist_items = data.checklist_items.filter(c => !c.is_deleted)`) to match the contract. Verify against `apiRest.tasksApi.list` output shape.

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Commit (Tasks 3–4)**

```bash
git add frontend/lib/apiSupabase.ts
git commit -m "feat(mobile): supabase authApi (Auth + workspace bootstrap) + tasksApi"
```

---

## Task 5: `notesApi` + `financeApi` CRUD

**Files:**
- Modify: `frontend/lib/apiSupabase.ts`

**Interfaces:**
- Produces: `notesApi` (`list, create, update, remove`) → `Note`; `financeApi` CRUD part (`listCategories, createCategory, removeCategory, listTransactions, createTransaction, updateTransaction, removeTransaction`) → `FinanceCategory`/`Transaction`. (`summary`/`report` added in Task 6.)

- [ ] **Step 1: Implement `notesApi` + finance CRUD**

```ts
// add to frontend/lib/apiSupabase.ts
import type { Note, FinanceCategory, Transaction } from "@/types";

export const notesApi = {
  list: async (): Promise<Note[]> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("notes").select("*")
      .eq("is_deleted", false).order("updated_at", { ascending: false });
    if (error) throw toApiException(error);
    return (data ?? []) as Note[];
  },
  create: async (payload: Partial<Note>): Promise<Note> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("notes")
      .insert({ ...payload, workspace_id: getWorkspaceId() }).select("*").single();
    if (error) throw toApiException(error);
    return data as Note;
  },
  update: async (id: string, payload: Partial<Note>): Promise<Note> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("notes").update(payload).eq("id", id).select("*").single();
    if (error) throw toApiException(error);
    return data as Note;
  },
  remove: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb.from("notes")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() }).eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
};

type TxQuery = { year?: number; month?: number; currency?: string; start?: string; end?: string; limit?: number; offset?: number };

const financeCrud = {
  listCategories: async (): Promise<FinanceCategory[]> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("finance_categories").select("*")
      .eq("is_deleted", false).order("name");
    if (error) throw toApiException(error);
    return (data ?? []) as FinanceCategory[];
  },
  createCategory: async (payload: { name: string; type: string }): Promise<FinanceCategory> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("finance_categories")
      .insert({ ...payload, workspace_id: getWorkspaceId() }).select("*").single();
    if (error) throw toApiException(error);
    return data as FinanceCategory;
  },
  removeCategory: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb.from("finance_categories")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() }).eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
  listTransactions: async (params?: TxQuery): Promise<Transaction[]> => {
    const sb = await getSupabase();
    let q = sb.from("transactions").select("*").eq("is_deleted", false);
    if (params?.currency) q = q.eq("currency", params.currency);
    if (params?.start) q = q.gte("transaction_date", params.start);
    if (params?.end) q = q.lte("transaction_date", params.end);
    if (params?.year && params?.month) {
      const mm = String(params.month).padStart(2, "0");
      const start = `${params.year}-${mm}-01`;
      const end = params.month === 12 ? `${params.year + 1}-01-01` : `${params.year}-${String(params.month + 1).padStart(2, "0")}-01`;
      q = q.gte("transaction_date", start).lt("transaction_date", end);
    }
    q = q.order("transaction_date", { ascending: false });
    if (params?.limit) q = q.limit(params.limit);
    const { data, error } = await q;
    if (error) throw toApiException(error);
    return (data ?? []) as Transaction[];
  },
  createTransaction: async (payload: Record<string, unknown>): Promise<Transaction> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("transactions")
      .insert({ ...payload, workspace_id: getWorkspaceId() }).select("*").single();
    if (error) throw toApiException(error);
    return data as Transaction;
  },
  updateTransaction: async (id: string, payload: Record<string, unknown>): Promise<Transaction> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("transactions").update(payload).eq("id", id).select("*").single();
    if (error) throw toApiException(error);
    return data as Transaction;
  },
  removeTransaction: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb.from("transactions")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() }).eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
};
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

---

## Task 6: `financeApi.summary` + `report` (client-side aggregation)

**Files:**
- Modify: `frontend/lib/apiSupabase.ts`

**Interfaces:**
- Consumes: `financeCrud.listTransactions`, types `FinanceSummary`, `FinanceReport`.
- Produces: full `financeApi = { ...financeCrud, summary, report }`. `summary(year, month, currency)` and `report({start,end,periodType,currency})` aggregate transactions client-side to match the REST aggregate shape.

- [ ] **Step 1: Confirm the aggregate shapes**

Read `frontend/types/index.ts` for `FinanceSummary` and `FinanceReport` exact fields (e.g. `total_income`, `total_expense`, `balance`, `count`, per-category/per-period breakdowns) and reproduce them exactly. Read `apiRest.financeApi.summary/report` to mirror rounding/sign conventions.

- [ ] **Step 2: Implement aggregation as a pure function + wire it**

```ts
// add to frontend/lib/apiSupabase.ts
import type { FinanceSummary, FinanceReport } from "@/types";

export function aggregateSummary(txns: Transaction[], currency: string): FinanceSummary {
  let total_income = 0, total_expense = 0;
  for (const t of txns) {
    const amt = Number(t.amount) || 0;
    if (t.type === "INCOME") total_income += amt;
    else total_expense += amt;
  }
  return {
    // shape MUST mirror @/types FinanceSummary — adjust field names to the real type:
    total_income, total_expense, balance: total_income - total_expense,
    currency, count: txns.length,
  } as FinanceSummary;
}

export const financeApi = {
  ...financeCrud,
  summary: async (year: number, month: number, currency = "IDR"): Promise<FinanceSummary> => {
    const txns = await financeCrud.listTransactions({ year, month, currency });
    return aggregateSummary(txns, currency);
  },
  report: async (payload: { start: string; end: string; periodType?: string; currency?: string }): Promise<FinanceReport> => {
    const currency = payload.currency ?? "IDR";
    const txns = await financeCrud.listTransactions({ start: payload.start, end: payload.end, currency });
    // Build the FinanceReport shape from @/types (periods/totals). Mirror apiRest.financeApi.report.
    return { /* fields per @/types FinanceReport */ } as FinanceReport;
  },
};
```

> **Note:** the `as FinanceSummary` / `as FinanceReport` casts are placeholders for the EXACT field set — Step 1 tells you the real fields; fill them in (no `any`, no missing required fields). This is the one place where the REST server did computation that now moves client-side (design §8.6).

- [ ] **Step 3: Typecheck + web build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: clean.

- [ ] **Step 4: Commit (Tasks 5–6)**

```bash
git add frontend/lib/apiSupabase.ts
git commit -m "feat(mobile): supabase notesApi + financeApi (CRUD + client-side summary/report)"
```

---

## Task 7: `calendarApi` + `routinesApi` (collapse to `calendar_events`)

**Files:**
- Modify: `frontend/lib/apiSupabase.ts`

**Interfaces:**
- Produces: `calendarApi` (`list, create, update, remove`) → `CalendarEvent`; `routinesApi` (`list, create, update, remove, generate, createBatch, syncStatus`) backed by the SAME `calendar_events` table (no `/routines` endpoint exists in Supabase, so the 404-fallback target IS the direct table). `generate` (AI) is unavailable on mobile → throw `ApiException("Routine generation runs on the desktop", "UNAVAILABLE_ON_MOBILE", 501)`. `syncStatus` returns `{ status: "supabase", configured: true }`.

- [ ] **Step 1: Implement calendar + routines**

```ts
// add to frontend/lib/apiSupabase.ts
import type { CalendarEvent } from "@/types";

async function calList(): Promise<CalendarEvent[]> {
  const sb = await getSupabase();
  const { data, error } = await sb.from("calendar_events").select("*")
    .eq("is_deleted", false).order("start_at", { ascending: true });
  if (error) throw toApiException(error);
  return (data ?? []) as CalendarEvent[];
}
async function calCreate(payload: Record<string, unknown>): Promise<CalendarEvent> {
  const sb = await getSupabase();
  const { data, error } = await sb.from("calendar_events")
    .insert({ ...payload, workspace_id: getWorkspaceId() }).select("*").single();
  if (error) throw toApiException(error);
  return data as CalendarEvent;
}
async function calUpdate(id: string, payload: Record<string, unknown>): Promise<CalendarEvent> {
  const sb = await getSupabase();
  const { data, error } = await sb.from("calendar_events").update(payload).eq("id", id).select("*").single();
  if (error) throw toApiException(error);
  return data as CalendarEvent;
}
async function calRemove(id: string): Promise<{ id: string }> {
  const sb = await getSupabase();
  const { error } = await sb.from("calendar_events")
    .update({ is_deleted: true, deleted_at: new Date().toISOString() }).eq("id", id);
  if (error) throw toApiException(error);
  return { id };
}

export const calendarApi = { list: calList, create: calCreate, update: calUpdate, remove: calRemove };

export const routinesApi = {
  list: calList,
  create: calCreate,
  update: calUpdate,
  remove: calRemove,
  createBatch: async (events: Record<string, unknown>[]): Promise<CalendarEvent[]> => {
    const sb = await getSupabase();
    const rows = events.map((e) => ({ ...e, workspace_id: getWorkspaceId() }));
    const { data, error } = await sb.from("calendar_events").insert(rows).select("*");
    if (error) throw toApiException(error);
    return (data ?? []) as CalendarEvent[];
  },
  generate: async (): Promise<never> => {
    throw new ApiException("Routine generation runs on the desktop app", "UNAVAILABLE_ON_MOBILE", 501, null);
  },
  syncStatus: async () => ({ status: "supabase", configured: true }),
};
```

> Match `routinesApi.createBatch`/`generate` signatures to `apiRest.routinesApi` exactly (param names/types). Confirm `generate`'s REST signature and return type before finalizing.

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

---

## Task 8: `automationsApi` + `weatherApi`

**Files:**
- Modify: `frontend/lib/apiSupabase.ts`

**Interfaces:**
- Produces: `automationsApi` (`list, create, update, remove`) → `Automation`; `weatherApi` (`listLocations, addLocation, removeLocation`) → `WeatherLocation`, plus `current` which is unavailable on mobile (live provider needs the backend secret) → throw `ApiException("Live weather runs on the desktop app", "UNAVAILABLE_ON_MOBILE", 501)`.

- [ ] **Step 1: Implement automations + weather**

```ts
// add to frontend/lib/apiSupabase.ts
import type { Automation, WeatherLocation, WeatherCurrent } from "@/types";

export const automationsApi = {
  list: async (): Promise<Automation[]> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("automations").select("*")
      .eq("is_deleted", false).order("created_at", { ascending: false });
    if (error) throw toApiException(error);
    return (data ?? []) as Automation[];
  },
  create: async (payload: Record<string, unknown>): Promise<Automation> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("automations")
      .insert({ ...payload, workspace_id: getWorkspaceId() }).select("*").single();
    if (error) throw toApiException(error);
    return data as Automation;
  },
  update: async (id: string, payload: Record<string, unknown>): Promise<Automation> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("automations").update(payload).eq("id", id).select("*").single();
    if (error) throw toApiException(error);
    return data as Automation;
  },
  remove: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb.from("automations")
      .update({ is_deleted: true, deleted_at: new Date().toISOString() }).eq("id", id);
    if (error) throw toApiException(error);
    return { id };
  },
};

export const weatherApi = {
  listLocations: async (): Promise<WeatherLocation[]> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("weather_locations").select("*").order("created_at");
    if (error) throw toApiException(error);
    return (data ?? []) as WeatherLocation[];
  },
  addLocation: async (name: string, isDefault = false): Promise<WeatherLocation> => {
    const sb = await getSupabase();
    const { data, error } = await sb.from("weather_locations")
      .insert({ name, is_default: isDefault, workspace_id: getWorkspaceId() }).select("*").single();
    if (error) throw toApiException(error);
    return data as WeatherLocation;
  },
  removeLocation: async (id: string): Promise<{ id: string }> => {
    const sb = await getSupabase();
    const { error } = await sb.from("weather_locations").delete().eq("id", id); // hard-delete (no is_deleted)
    if (error) throw toApiException(error);
    return { id };
  },
  current: async (_location?: string): Promise<WeatherCurrent> => {
    throw new ApiException("Live weather runs on the desktop app", "UNAVAILABLE_ON_MOBILE", 501, null);
  },
};
```

- [ ] **Step 2: Typecheck + web build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: clean.

- [ ] **Step 3: Commit (Tasks 7–8)**

```bash
git add frontend/lib/apiSupabase.ts
git commit -m "feat(mobile): supabase calendar/routines/automations/weather APIs"
```

---

## Task 9: Build wiring (`build:mobile` env + APK workflow)

**Files:**
- Modify: `frontend/package.json`
- Modify: `.github/workflows/android-apk.yml`

**Interfaces:**
- Produces: a `build:mobile` that bakes `NEXT_PUBLIC_DATA_MODE=supabase` + `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`; the workflow passes those from repo variables/secrets.

- [ ] **Step 1: Extend `build:mobile`**

```json
"build:mobile": "cross-env BUILD_TARGET=mobile NEXT_PUBLIC_AUTH_MODE=bearer NEXT_PUBLIC_DATA_MODE=supabase next build",
```
(`NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` come from the environment — set locally in `.env.local` for dev, and in the workflow `env:` for CI. Do NOT hardcode keys in `package.json`.)

- [ ] **Step 2: Bake the vars in the APK workflow**

In `.github/workflows/android-apk.yml`, extend the build step `env:` block:

```yaml
      - name: Build static export + sync Capacitor
        env:
          NEXT_PUBLIC_API_BASE_URL: ${{ env.API_URL }}
          NEXT_PUBLIC_SUPABASE_URL: ${{ vars.SUPABASE_URL }}
          NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
          # build:mobile sets NEXT_PUBLIC_AUTH_MODE=bearer + NEXT_PUBLIC_DATA_MODE=supabase
        run: |
          echo "Building Supabase-mode APK"
          npm run build:mobile
          npx cap sync android
```

Add `SUPABASE_URL` (repo Variable) and `SUPABASE_ANON_KEY` (repo Secret) in GitHub settings — document this in the runbook. The anon key is publishable, but use a Secret to keep it out of logs.

- [ ] **Step 3: Verify the mobile build compiles in Supabase mode**

Run:
```bash
cd frontend && NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co \
  NEXT_PUBLIC_SUPABASE_ANON_KEY=test-anon-key npm run build:mobile
```
Expected: static export builds; `supabase-js` is bundled; `DATA_MODE` true wires `apiSupabase`. (No device needed — this is the compile/bundle gate.)

---

## Task 10: Mobile session hydration in `AppShell` + final verification

**Files:**
- Modify: `frontend/components/layout/AppShell.tsx`

**Interfaces:**
- Consumes: `DATA_MODE`, `getSupabase`, `authApi.me`.
- Produces: on cold start in Supabase mode, the Supabase session is restored (via persisted storage) before the first `authApi.me()` query, mirroring today's `hydrateBearerToken().then(authApi.me())` ordering.

- [ ] **Step 1: Hook Supabase hydration into the existing effect**

In `AppShell.tsx`, where it currently does `hydrateBearerToken().then(() => authApi.me())`, branch on `DATA_MODE`:

```ts
import { DATA_MODE, getSupabase } from "@/lib/supabaseClient";

// inside the bootstrap effect:
const hydrate = DATA_MODE
  ? getSupabase().then((sb) => sb.auth.getSession()).then(() => undefined)  // restores persisted session
  : hydrateBearerToken();

hydrate
  .then(() => authApi.me())
  .then((me) => { setStoredUser(me.user); authConfirmed = true; setReady(true); })
  .catch(() => { authConfirmed = false; clearAuth(); router.replace("/login"); });
```

> `supabase-js` with `persistSession: true` auto-restores from the Capacitor storage adapter; awaiting `getSession()` guarantees the session is loaded before `me()` runs. Keep the bearer path untouched for web/desktop.

- [ ] **Step 2: Typecheck + both builds**

Run:
```bash
cd frontend && npx tsc --noEmit && npm run build && \
  NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co \
  NEXT_PUBLIC_SUPABASE_ANON_KEY=test npm run build:mobile
```
Expected: web build (REST mode) and mobile build (Supabase mode) both succeed.

- [ ] **Step 3: Manual verification (document in the PR)**

Against a real Supabase project with the schema from Plan 1 stood up and a provisioned user:
1. `npm run build:mobile` with real `NEXT_PUBLIC_SUPABASE_*`, run the static export (or APK), log in → lands on dashboard (Supabase Auth session).
2. Create a task / note / transaction on mobile → row appears in Supabase (and syncs to desktop via Plan 2).
3. Kill + reopen the app → still logged in (session persisted).
4. Confirm a second user cannot see the first user's rows (RLS).

- [ ] **Step 4: Commit (Tasks 9–10)**

```bash
git add frontend/package.json .github/workflows/android-apk.yml frontend/components/layout/AppShell.tsx
git commit -m "feat(mobile): build wiring (DATA_MODE=supabase) + session hydration"
```

---

## Self-Review

**Spec coverage (design §8 Component D):**
- §8.1 one new impl behind the seam, `DATA_MODE` const → Task 2. ✓
- §8.2 same unwrapped shapes + `ApiException`-compatible errors (401/403/PGRST mapping) → Task 2 mapper, used everywhere. ✓
- §8.3 lazy `import()` of `supabase-js`, pinned + lockfile → Task 1. ✓
- §8.4 build wiring (`NEXT_PUBLIC_DATA_MODE`/url/anon in `build:mobile` + workflow) → Task 9. ✓
- §8.5 mobile Supabase Auth login + hydration before first query → Tasks 3, 10. ✓
- §8.6 v3.7 port scope (auth, tasks, notes, finance, calendar, automations, weather, dashboard) → Tasks 3–8; dashboard composes from tasks/notes/finance (no new surface). Compute/file groups stay REST/hidden. ✓

**Placeholder scan:** Two intentional "fill the exact `@/types` fields" notes (Task 6 `FinanceSummary`/`FinanceReport` shapes) with explicit instructions to read the real type — not lazy placeholders; the aggregation logic is complete. The `as Type` casts are flagged for the implementer to complete the field set.

**Type consistency:** `getWorkspaceId()`/`setWorkspaceId()` used consistently (Tasks 1, 3–8); `toApiException` signature stable; `authApi`/`tasksApi`/... method signatures copied verbatim from the REST research (verb/params/return). `routinesApi` collapses to `calendar_events` so the REST 404-fallback is satisfied by direct table access. `weatherApi.current` + `routinesApi.generate` correctly throw `UNAVAILABLE_ON_MOBILE` rather than silently breaking.

**Out of scope (deferred to 3.8/3.9):** `aiApi`, `memoryApi`, `knowledgeApi`, `driveApi`, `systemApi`, `n8nApi`, `googleApi`, `weatherApi.current`, `routinesApi.generate` — Edge Functions + Storage. These stay on REST/hidden on mobile.
