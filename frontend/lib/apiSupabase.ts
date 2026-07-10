// frontend/lib/apiSupabase.ts — Supabase-backed seam. Groups are replaced with real
// Supabase impls task-by-task in later pairs; until then they passthrough to REST.
//
// Compute/file groups (ai/memory/knowledge/drive/system/n8n/google/settings) are NOT
// ported in 3.7 — re-export the REST impl (they are hidden on mobile UI).
export {
  notesApi,
  financeApi,
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
