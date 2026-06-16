// frontend/lib/api.ts — selects the data implementation at build time.
// When NEXT_PUBLIC_DATA_MODE=supabase the Supabase-backed impl is used;
// otherwise falls back to the REST impl (web/desktop default).
import { DATA_MODE } from "@/lib/supabaseClient";

export { ApiException, getApiBaseUrl } from "@/lib/apiRest";
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
// aiApi + memoryApi are HYBRID: proposal/suggestion reads + accept/reject/edit go
// Supabase-direct on mobile so the pending list is shared with desktop; chat/providers
// stay REST. (On desktop impl=rest, so these are the full REST impls.)
export const aiApi = impl.aiApi;
export const memoryApi = impl.memoryApi;
// remaining compute/file groups always come from REST (hidden on mobile UI)
export const knowledgeApi = rest.knowledgeApi;
export const driveApi = rest.driveApi;
export const systemApi = rest.systemApi;
export const n8nApi = rest.n8nApi;
export const googleApi = rest.googleApi;
export const settingsApi = rest.settingsApi;
