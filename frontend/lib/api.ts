// frontend/lib/api.ts — selects the data implementation at build time.
// When NEXT_PUBLIC_DATA_MODE=supabase the Supabase-backed impl is used;
// otherwise falls back to the REST impl (web/desktop default).
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
export const automationsApi = impl.automationsApi;
// compute/file groups always come from REST (hidden on mobile in v3.7)
export const aiApi = rest.aiApi;
export const memoryApi = rest.memoryApi;
export const knowledgeApi = rest.knowledgeApi;
export const driveApi = rest.driveApi;
export const systemApi = rest.systemApi;
export const n8nApi = rest.n8nApi;
export const googleApi = rest.googleApi;
export const settingsApi = rest.settingsApi;
