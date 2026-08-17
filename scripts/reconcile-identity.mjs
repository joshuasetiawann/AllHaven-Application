// One-off: merge the two accidental identities for the same person.
//
// The desktop account was created locally first (profile 93c2c93e / workspace
// c958322e, supabase_user_id NULL). Signing up on the phone later created a
// SECOND identity inside Supabase (profile 51e4b5c7 / workspace 2a052a49, bound
// to auth user 8cf7aba2). The mirror has been failing every 15 seconds since:
//
//   23505 duplicate key value violates unique constraint "ix_profiles_email"
//
// Pushing the local profile tries to INSERT (its primary key is absent upstream)
// and collides with the phone profile's email. profiles failing drags 12 of 25
// tables down with it — and the differing workspace ids mean nothing would line
// up even if the push succeeded.
//
// This makes Supabase adopt the DESKTOP identity: the smaller change, and the
// phone keeps working because its auth link (supabase_user_id) moves onto the
// surviving profile.
//
// Rows are deleted and re-inserted rather than UPDATEd in place. The composite
// foreign keys (chat_messages -> chat_sessions on (workspace_id, session_id))
// are NO ACTION and not deferrable, so changing workspace_id on either side
// alone violates them mid-statement.
//
//   node scripts/reconcile-identity.mjs --dry-run   # print the plan, change nothing
//   node scripts/reconcile-identity.mjs             # apply
//
// Pass the Supabase backup taken before the run as the first argument, or leave
// it out to pick the newest supabase-*.json in ../../allhaven-backups.
// The service_role key is read from the running backend container, so it never
// has to be written down here.

import { execSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const DEFAULT_BACKUP_DIR = resolve(HERE, "../../../allhaven-backups");
const DRY = process.argv.includes("--dry-run");
const ARG = process.argv.slice(2).find((a) => !a.startsWith("--"));

const OLD_P = "51e4b5c7-c2e3-429a-843d-9781250e3a7a"; // phone-created profile
const OLD_W = "2a052a49-11ae-4c88-9a4e-4a6013e3afb4"; // phone-created workspace
const NEW_P = "93c2c93e-e6d1-4598-8670-5e9d546135a5"; // desktop profile (survives)
const NEW_W = "c958322e-32f7-4130-b2c7-aa0dd3444029"; // desktop workspace (survives)
const AUTH = "8cf7aba2-fc31-4230-9650-d4a58e0bf332";  // the phone's Supabase login
const EMAIL = "07joshua2020@gmail.com";
const STAMP = "2026-08-14T07:43:05.705396+00:00";     // desktop identity's created_at

// Parents before children: inserts follow this order, deletes reverse it.
const ORDER = [
  "chat_sessions",
  "chat_messages",
  "ai_multi_agent_runs",
  "ai_agent_responses",
  "transactions",
  "calendar_events",
];

const BASE = "https://tsilfsbmdarvtardbgrw.supabase.co/rest/v1";
const sh = (cmd) => execSync(cmd, { encoding: "utf8" }).trim();

const KEY = sh("docker exec allhaven-prod-backend-1 printenv SUPABASE_SERVICE_ROLE_KEY");
if (!KEY) throw new Error("could not read SUPABASE_SERVICE_ROLE_KEY from allhaven-prod-backend-1");
const H = { apikey: KEY, Authorization: `Bearer ${KEY}`, "Content-Type": "application/json" };

async function call(method, path, body, prefer) {
  const label = `${method} ${path}`;
  if (DRY) { console.log(`  would ${label}`); return null; }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: prefer ? { ...H, Prefer: prefer } : H,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${label} -> HTTP ${res.status} ${text}`);
  console.log(`  ok  ${label}`);
  return text ? JSON.parse(text) : null;
}

// Swap every reference to the retired identity, whatever the column is called.
const repoint = (row) =>
  Object.fromEntries(
    Object.entries(row).map(([k, v]) => [k, v === OLD_W ? NEW_W : v === OLD_P ? NEW_P : v]),
  );

function loadBackup() {
  if (ARG) return { path: ARG, data: JSON.parse(readFileSync(ARG, "utf8")) };
  if (!existsSync(DEFAULT_BACKUP_DIR)) {
    throw new Error(`no backup given and ${DEFAULT_BACKUP_DIR} does not exist`);
  }
  const file = readdirSync(DEFAULT_BACKUP_DIR)
    .filter((n) => n.startsWith("supabase-") && n.endsWith(".json")).sort().pop();
  if (!file) throw new Error(`no supabase-*.json in ${DEFAULT_BACKUP_DIR} — take a backup first`);
  const path = join(DEFAULT_BACKUP_DIR, file);
  return { path, data: JSON.parse(readFileSync(path, "utf8")) };
}

async function main() {
  const { path, data } = loadBackup();
  console.log(`backup: ${path}${DRY ? "   (DRY RUN — nothing will change)" : ""}`);

  const rows = Object.fromEntries(
    ORDER.map((t) => [t, (data[t] ?? []).filter((r) => r.workspace_id === OLD_W)]),
  );
  const total = Object.values(rows).reduce((n, r) => n + r.length, 0);
  console.log("rows to move:", ORDER.map((t) => `${t}=${rows[t].length}`).join(" "), `(${total} total)`);
  if (!total) console.log("  (nothing to move — the phone's rows may already have been migrated)");

  console.log("\n1. free the unique indexes held by the phone profile");
  await call("PATCH", `/profiles?id=eq.${OLD_P}`,
    { email: `retired-${OLD_P}@allhaven.invalid`, supabase_user_id: null }, "return=minimal");

  console.log("\n2. bring the desktop identity into Supabase");
  const workspace = (data.workspaces ?? []).find((w) => w.id === NEW_W) ?? {
    id: NEW_W, name: "Joshua Setiawan's Workspace", owner_id: NEW_P,
    created_at: STAMP, updated_at: STAMP,
  };
  await call("POST", "/workspaces", [workspace], "resolution=merge-duplicates,return=minimal");
  await call("POST", "/profiles", [{
    id: NEW_P, email: EMAIL, full_name: "Joshua Setiawan",
    created_at: STAMP, updated_at: STAMP,
    supabase_user_id: AUTH, // the phone's login now resolves to THIS profile
  }], "resolution=merge-duplicates,return=minimal");
  await call("POST", "/workspace_members", [{
    id: "10400ca9-7f96-45a1-9f77-334159f56171",
    workspace_id: NEW_W, user_id: NEW_P, role: "owner",
    created_at: STAMP, updated_at: STAMP,
  }], "resolution=merge-duplicates,return=minimal");

  console.log("\n3. move the phone's rows across (delete child-first, insert parent-first)");
  for (const t of [...ORDER].reverse()) {
    if (rows[t].length) await call("DELETE", `/${t}?workspace_id=eq.${OLD_W}`, undefined, "return=minimal");
  }
  for (const t of ORDER) {
    if (rows[t].length) await call("POST", `/${t}`, rows[t].map(repoint), "return=minimal");
  }

  console.log("\n4. retire the duplicate identity");
  await call("DELETE", `/workspace_members?workspace_id=eq.${OLD_W}`, undefined, "return=minimal");
  await call("DELETE", `/profiles?id=eq.${OLD_P}`, undefined, "return=minimal");
  await call("DELETE", `/workspaces?id=eq.${OLD_W}`, undefined, "return=minimal");

  console.log("\n5. link the desktop profile to the Supabase auth user, locally");
  const sql = `update profiles set supabase_user_id='${AUTH}' where id='${NEW_P}';`;
  if (DRY) console.log(`  would run: ${sql}`);
  else console.log("  " + sh(`docker exec allhaven-prod-db-1 psql -U allhaven -d allhaven -c "${sql}"`));

  console.log(`\n${DRY ? "dry run complete — rerun without --dry-run to apply." : "done."}`);
  if (!DRY) {
    console.log("Next:");
    console.log("  docker restart allhaven-prod-backend-1");
    console.log("  docker logs -f allhaven-prod-backend-1 | grep -i sync");
    console.log("'12/25 tables failed' should stop appearing. Sign in again on the phone.");
  }
}

main().catch((e) => { console.error("\nFAILED:", e.message); process.exit(1); });
