// The mobile app talks to Supabase directly, so a select that disagrees with the
// live schema fails only on a real phone — exactly how the task list, chat
// history and AI Knowledge broke: an embed PostgREST called ambiguous
// (PGRST201, two FKs from task_checklist_items to tasks) and a column the API
// calls "meta" but the database calls "metadata".
//
// This probes every column list the Supabase impl selects against the real
// project. Reads only; RLS returns [] for the anon key, which is a pass — we are
// checking the QUERY is valid, not that rows are visible.
//
//   node --test tests/supabase-mobile-queries.test.cjs
//
// Credentials come from frontend/.env.local (or SUPABASE_URL/SUPABASE_ANON_KEY).
// Skipped when neither is present, so CI without secrets stays green.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

function credentials() {
  let url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "";
  let key = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
  const envFile = path.join(__dirname, "../frontend/.env.local");
  if ((!url || !key) && fs.existsSync(envFile)) {
    for (const line of fs.readFileSync(envFile, "utf8").split(/\r?\n/)) {
      const m = line.match(/^\s*(NEXT_PUBLIC_SUPABASE_URL|NEXT_PUBLIC_SUPABASE_ANON_KEY)\s*=\s*(.+?)\s*$/);
      if (!m) continue;
      if (m[1].endsWith("URL")) url ||= m[2];
      else key ||= m[2];
    }
  }
  return { url: url.replace(/\/$/, ""), key };
}

// table -> the exact select the mobile impl sends (lib/apiSupabase.ts).
const QUERIES = {
  tasks: "*, checklist_items:task_checklist_items!fk_task_checklist_items_task_id_tasks(*)",
  chat_groups: "id,name,created_at,updated_at",
  chat_sessions: "id,title,group_id,section_key,created_at,updated_at",
  chat_messages: "id,session_id,role,content,section_key,meta:metadata,created_at",
  ai_knowledge_documents:
    "id,title,filename,mime_type,size_bytes,status,chunk_count,last_indexed_at,error_message,meta:metadata,created_at,updated_at",
  ai_tool_proposals:
    "id,tool_name,tool_payload,status,risk_level,requires_confirmation,error_message,executed_at,created_at,updated_at",
};

test("every mobile Supabase select matches the live schema", async (t) => {
  const { url, key } = credentials();
  if (!url || !key) {
    t.skip("no Supabase credentials (set NEXT_PUBLIC_SUPABASE_* in frontend/.env.local)");
    return;
  }
  const failures = [];
  for (const [table, select] of Object.entries(QUERIES)) {
    const target = `${url}/rest/v1/${table}?select=${encodeURIComponent(select)}&limit=1`;
    const res = await fetch(target, { headers: { apikey: key, Authorization: `Bearer ${key}` } });
    const body = await res.text();
    // 200 + "[]" is the healthy shape: query valid, RLS hides the rows.
    if (res.status !== 200) failures.push(`${table}: HTTP ${res.status} ${body.slice(0, 200)}`);
  }
  assert.deepEqual(failures, [], `broken mobile queries:\n${failures.join("\n")}`);
});
