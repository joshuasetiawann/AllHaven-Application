// frontend/lib/supabaseError.ts — maps PostgREST / Auth errors to ApiException.
// Import from apiRest (NOT api) to avoid a circular import through the selector.
import { ApiException } from "@/lib/apiRest";

// PostgrestError: { message, details, hint, code }. AuthError: { message, status }.
export function toApiException(error: unknown, fallbackStatus = 400): ApiException {
  const e = error as { message?: string; code?: string; status?: number; name?: string; details?: unknown };
  const message = e?.message || "Supabase request failed";
  const code = e?.code || "SUPABASE_ERROR";
  let statusCode = typeof e?.status === "number" ? e.status : fallbackStatus;
  // Network / abort / timeout: no HTTP status. Surface as statusCode 0 so
  // connection.isBackendUnreachable() fires and the UI shows a "connection slow /
  // unreachable, try again" state instead of a frozen spinner or a raw 400.
  if (
    e?.name === "AbortError" ||
    code === "TIMEOUT" ||
    /\b(fetch failed|failed to fetch|networkerror|network error|timed out|timeout|aborted|load failed)\b/i.test(message)
  ) {
    return new ApiException(
      /timed out|timeout|aborted/i.test(message)
        ? "The connection is slow or unreachable — please try again."
        : message,
      "TIMEOUT",
      0,
      e?.details ?? error,
    );
  }
  // Unique-violation (e.g. the cross-device dedup_key index): the change was already
  // applied — usually by the other device. Treat as a friendly 409, not a raw 400.
  if (code === "23505") {
    return new ApiException(
      "This change was already applied (possibly on another device).",
      "ALREADY_APPLIED",
      409,
      e?.details ?? error,
    );
  }
  // PostgREST RLS / auth failures surface as 401/403 so handleUnauthorized + fallbacks fire correctly.
  if (code === "PGRST301" || code === "42501") statusCode = 403;
  if (e?.status === 401) statusCode = 401;
  if (code === "PGRST116") {
    // 0 rows on a single-row request: the item doesn't exist, or RLS filtered it
    // out (it's in another workspace, or the session expired). The raw PostgREST
    // text ("JSON object requested, multiple (or no) rows returned") is useless to
    // a user — replace it with something actionable.
    return new ApiException(
      "This item couldn't be found in your current workspace. Try signing out and back in.",
      code,
      404,
      e?.details ?? error,
    );
  }
  return new ApiException(message, code, statusCode, e?.details ?? error);
}
