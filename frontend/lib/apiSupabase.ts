// frontend/lib/apiSupabase.ts — Supabase-backed seam. Groups are replaced with real
// Supabase impls task-by-task in later pairs; until then they passthrough to REST.
export {
  authApi,
  tasksApi,
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
