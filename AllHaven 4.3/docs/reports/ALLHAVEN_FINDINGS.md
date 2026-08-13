# AllHaven Findings

> Historical baseline finding details. ALL-001 through ALL-010 are now closed and
> retested; see `ALLHAVEN_REMEDIATION_REPORT.md` for current status and evidence.

Baseline-only audit. **No application fix was applied.** Findings are ordered by real-world priority, with runtime-confirmed issues separated from source-evident risks.

## ALL-001 — Docker System Control reports healthy containers as stopped

- **Severity:** HIGH
- **Type:** Fake Signal / Reliability
- **Confidence:** CONFIRMED
- **Component:** System Control, `backend/app/services/system_service.py:220-248`, `/dashboard/settings/system`
- **Preconditions:** Production-local Docker deployment; Haven Agent unavailable, so fallback probing is used.
- **Steps to reproduce:** Start the production-local frontend, backend, and PostgreSQL containers. Confirm them with `docker ps`. Open Settings → System Control.
- **Expected:** The three running containers are shown running, or the application clearly says it cannot determine their state.
- **Actual:** Docker showed frontend and backend up and PostgreSQL healthy. UI reported `Running 1/3`, with Frontend and PostgreSQL `stopped`, while also displaying `No services need attention`.
- **Evidence:** Runtime comparison between `docker ps` and System Control. Fallback code probes ports on `_AGENT_HOST = 127.0.0.1`; inside the backend container, that loopback cannot see sibling frontend/DB containers.
- **Root cause:** Container topology is treated like a single-host process layout; the fallback port probe is namespace-local to the backend container. UI summary logic also contradicts its own stopped-service count.
- **Impact:** A user may troubleshoot or restart the wrong component, overlook an actual outage, or distrust the health dashboard. Operational truth is a prerequisite for safe daily use.
- **Recommended fix:** Make fallback probes deployment-aware (Docker DNS/service health or backend-configured endpoints), return `unknown` when not observable, and derive the attention banner from the same normalized status model.
- **Retest procedure:** Compare every displayed service state against Docker health in healthy, stopped, restarting, and unreachable scenarios; verify the summary banner for each.

## ALL-002 — Upload limit is checked only after the entire body is in memory

- **Severity:** HIGH
- **Type:** Security / Reliability / Performance
- **Confidence:** HIGH-CONFIDENCE CODE ISSUE
- **Component:** `backend/app/api/routers/drive.py:46-58`, `backend/app/api/routers/knowledge.py:30-43`, associated services
- **Preconditions:** Authenticated user able to upload Drive or Knowledge content.
- **Steps to reproduce:** Review both upload routers and follow the call to the service-level size check. A destructive oversized runtime payload was intentionally not sent.
- **Expected:** Request/body size is capped by server/proxy and/or streamed with an early byte limit before large allocation.
- **Actual:** Both routers execute `data = await file.read()` first. `len(data)` is checked later in `drive_service.py:71-75` and `knowledge_service.py:352-360`.
- **Evidence:** Direct source trace. No earlier application/proxy request-body cap was found in the audited configuration.
- **Root cause:** Validation is placed after materializing the complete upload as `bytes`.
- **Impact:** A valid account can cause memory pressure, worker termination, or denial of service with a request far larger than the nominal 250 MB limit.
- **Recommended fix:** Enforce a reverse-proxy/ASGI body cap and stream to bounded temporary storage while counting bytes; abort and remove partial data immediately at the limit.
- **Retest procedure:** Send just-below, exact-limit, just-above, and many-times-limit chunked bodies while measuring process RSS and response time. The oversized body must be rejected without proportional memory growth.

## ALL-003 — Mobile bearer and Supabase sessions use non-secure Preferences storage

- **Severity:** HIGH
- **Type:** Security
- **Confidence:** HIGH-CONFIDENCE CODE ISSUE
- **Component:** `frontend/lib/mobileAuth.ts:21-80`, `frontend/lib/supabaseClient.ts:19-33`
- **Preconditions:** Capacitor mobile build in bearer/Supabase mode.
- **Steps to reproduce:** Inspect token persistence and Capacitor's storage semantics; device extraction was blocked by lack of emulator/device.
- **Expected:** Long-lived bearer/refresh credentials are stored using Android Keystore/iOS Keychain-backed secure storage.
- **Actual:** `allhaven_bearer_token` and Supabase session values are persisted using `@capacitor/preferences`.
- **Evidence:** Source locations above. Capacitor documents Preferences as UserDefaults on iOS and SharedPreferences on Android and points to secure storage for more robust encrypted storage: https://capacitorjs.com/docs/apis/preferences
- **Root cause:** Native persistence was equated with secret-safe persistence; Preferences is not a credential vault.
- **Impact:** On a compromised/rooted device, insecure backup, or filesystem extraction, a reusable API/Supabase session may be exposed.
- **Recommended fix:** Move credentials to a maintained Keychain/Keystore-backed plugin, minimize token lifetime, rotate refresh tokens, and clear secure storage on logout/revocation.
- **Retest procedure:** Inspect application data/backup on Android and iOS; verify no plaintext/reversibly stored bearer or refresh token outside protected keystore/keychain storage.

## ALL-004 — Database schema enforces almost no referential integrity

- **Severity:** HIGH
- **Type:** Data Integrity
- **Confidence:** HIGH-CONFIDENCE CODE ISSUE
- **Component:** PostgreSQL public schema / SQLAlchemy migrations
- **Preconditions:** Any partial write, direct SQL/admin action, sync race, failed cleanup, or application bug.
- **Steps to reproduce:** Query `information_schema.table_constraints` for foreign keys and compare with relationship columns (`workspace_id`, `created_by`, `owner_id`, `user_id`, category/session/document references).
- **Expected:** Core ownership and parent-child relationships are enforced by foreign keys with intentional delete behavior.
- **Actual:** The complete public schema has one foreign key only: `task_checklist_items.task_id → tasks.id`. Workspace ownership, profile/user, session/user, finance/category, chat/session, knowledge/chunk, and most other relationships have none.
- **Evidence:** Runtime schema query at migration head `0020_ai_memory_soft_delete`: `FK_COUNT=1`. Current representative orphan counts were zero after audit cleanup, so this is a structural risk—not a claim of existing corruption.
- **Root cause:** Referential rules are implemented mainly in application services and sync logic rather than the database.
- **Impact:** Orphans, cross-entity inconsistency, and incomplete cascades can survive permanently after a race, migration, sync, or partial failure.
- **Recommended fix:** Inventory every logical relationship, clean/validate existing rows, add indexed foreign keys with explicit `ON DELETE` behavior in staged migrations, and keep application checks as defense in depth.
- **Retest procedure:** Verify constraint inventory; attempt invalid parent references; delete parent rows; run orphan queries across every relationship; test migrations on a production-like copy.

## ALL-005 — Task deletion is immediate with no confirmation or undo

- **Severity:** MEDIUM
- **Type:** UX / Data Integrity
- **Confidence:** CONFIRMED
- **Component:** `/dashboard/tasks`
- **Preconditions:** Authenticated user with a task.
- **Steps to reproduce:** Create a task and select the `Delete task` icon.
- **Expected:** Confirmation, undo window, recycle bin, or another explicit safeguard precedes irreversible deletion.
- **Actual:** The task disappears immediately after one click; no confirmation dialog or undo action is offered. Backend follow-up confirmed the row was deleted (subsequent GET 404).
- **Evidence:** Browser UI workflow plus API state verification.
- **Root cause:** The destructive control is wired directly to delete without an interlock or recoverable deletion model.
- **Impact:** A misclick can permanently remove a real command and its checklist.
- **Recommended fix:** Require an accessible confirmation containing the task title and preferably use soft delete/undo with delayed purge.
- **Retest procedure:** Exercise cancel/confirm, keyboard activation, double-click, slow network, duplicate requests, and undo across two tabs.

## ALL-006 — Production frontend dependency tree contains four high-severity audit findings

- **Severity:** MEDIUM
- **Type:** Security / Dependency
- **Confidence:** CONFIRMED
- **Component:** `frontend/package-lock.json`; installed Next.js 15.5.19, PostCSS 8.5.15, nanoid 3.3.12, sharp 0.34.5
- **Preconditions:** Exploitability varies by advisory and feature path.
- **Steps to reproduce:** Run `npm audit --omit=dev --json` from `frontend`.
- **Expected:** No known high-severity production dependency findings.
- **Actual:** npm reported four high package findings (`next`, `postcss`, `nanoid`, `sharp`) and offered a non-major Next upgrade path.
- **Evidence:** npm audit output and advisories: https://github.com/advisories/GHSA-m99w-x7hq-7vfj, https://github.com/advisories/GHSA-89xv-2m56-2m9x, https://github.com/advisories/GHSA-p9j2-gv94-2wf4, https://github.com/advisories/GHSA-r28c-9q8g-f849, https://github.com/advisories/GHSA-28wg-ghj8-5hjv, https://github.com/advisories/GHSA-f88m-g3jw-g9cj
- **Root cause:** Locked versions predate available patched releases.
- **Impact:** Current source does not use Server Actions or rewrites and does not appear to process attacker-controlled CSS at runtime, reducing several listed exploit paths. Nevertheless, the production tree remains on vulnerable version ranges and future feature changes can activate them.
- **Recommended fix:** Upgrade through the supported patched Next/PostCSS/nanoid/sharp graph, review all transitive changes, rebuild, rerun full tests, and verify Image Optimization and caching behavior.
- **Retest procedure:** Rerun npm audit and confirm zero high/critical production findings; then run build, route smoke, header, image, cache, and API regression tests.

## ALL-007 — Production integration secrets use a custom MVP cryptographic construction

- **Severity:** MEDIUM
- **Type:** Security
- **Confidence:** HIGH-CONFIDENCE CODE ISSUE
- **Component:** `backend/app/core/secrets.py:1-75`
- **Preconditions:** Provider/integration secrets are saved in AllHaven settings.
- **Steps to reproduce:** Trace `encrypt_secret`/`decrypt_secret` and the integration configuration persistence path.
- **Expected:** Vetted, maintained authenticated encryption (for example AES-GCM/Fernet via a reviewed library) or a managed KMS/secret store with rotation support.
- **Actual:** Production code derives a SHA-256 counter-mode keystream, XORs plaintext, then applies HMAC-SHA256. The file itself labels this a standard-library-only `MVP encryption scheme` and recommends replacement.
- **Evidence:** Source lines 1-9 and 30-75. Tamper detection exists; this finding does not claim plaintext storage or a demonstrated cryptographic break.
- **Root cause:** An MVP dependency-avoidance tradeoff remained in the production path.
- **Impact:** Custom constructions have a larger review/maintenance risk, no standard token/version/rotation story, and can make migration or incident response fragile.
- **Recommended fix:** Version ciphertext envelopes and migrate to a vetted AEAD/KMS design, with key rotation, backward-compatible decrypt/re-encrypt, and documented backup/recovery behavior.
- **Retest procedure:** Validate tamper rejection, nonce uniqueness, key rotation, legacy migration, wrong-key behavior, backup restore, and log/API redaction.

## ALL-008 — DOCX extraction has no decompressed-size or compression-ratio limit

- **Severity:** MEDIUM
- **Type:** Security / Reliability
- **Confidence:** HIGH-CONFIDENCE CODE ISSUE
- **Component:** `backend/app/services/knowledge_service.py:187-211`
- **Preconditions:** Authenticated user uploads a DOCX within compressed upload limit.
- **Steps to reproduce:** Review `_extract_docx`; a live archive bomb was intentionally not generated or uploaded.
- **Expected:** Validate ZIP entry count, individual and cumulative uncompressed size, and compression ratio before reading XML.
- **Actual:** Selected entries are loaded using `archive.read(name)` and parsed, with no bounds based on `ZipInfo.file_size` or cumulative expanded bytes.
- **Evidence:** Direct source trace. XML parser hardening does not bound ZIP decompression memory.
- **Root cause:** Compressed input size is validated, but expanded archive size is not.
- **Impact:** A small authenticated upload can expand into very large memory consumption and deny service.
- **Recommended fix:** Reject suspicious ratios and excessive entry/cumulative uncompressed sizes before reading; stream within a strict extraction budget.
- **Retest procedure:** Test normal DOCX, high-ratio archive, many-entry archive, oversized XML, corrupt ZIP, and concurrent uploads while monitoring RSS/CPU.

## ALL-009 — Production-local CORS rejects the valid `127.0.0.1` frontend origin

- **Severity:** MEDIUM
- **Type:** Functional / Reliability
- **Confidence:** CONFIRMED
- **Component:** `docker-compose.prod.local.yml:32`, backend CORS middleware
- **Preconditions:** User opens the locally exposed frontend as `http://127.0.0.1:3000` rather than `http://localhost:3000`.
- **Steps to reproduce:** Open that origin, submit registration/login, and observe preflight/network/backend logs.
- **Expected:** Either the alias works consistently or the frontend redirects to the canonical origin before authentication.
- **Actual:** Page loads, but OPTIONS for `/auth/register` returns 400 and the UI reports that it cannot reach the API. The same credentials and action work on `http://localhost:3000`.
- **Evidence:** Browser reproduction, backend OPTIONS log, and Compose allowlist containing localhost/Capacitor origins but not `http://127.0.0.1:3000`.
- **Root cause:** The frontend binds on all interfaces while CORS allows only one loopback spelling.
- **Impact:** A common local URL appears healthy until the first API action, creating a confusing broken-login experience.
- **Recommended fix:** Choose and enforce one canonical URL (redirect aliases) or explicitly allow the intended loopback origins consistently with cookie/CSRF policy.
- **Retest procedure:** Test registration/login/logout and CSRF from localhost, IPv4 loopback, IPv6 loopback if supported, LAN/Tailscale origin, and rejected hostile origins.

## ALL-010 — Production CSP allows inline scripts

- **Severity:** LOW
- **Type:** Security
- **Confidence:** CONFIRMED
- **Component:** `frontend/next.config.js:28-45`
- **Preconditions:** A separate HTML/script injection primitive exists.
- **Steps to reproduce:** Inspect production `Content-Security-Policy` response header.
- **Expected:** Scripts use nonces/hashes (and optionally `strict-dynamic`) without a blanket inline-script allowance.
- **Actual:** Header includes `script-src 'self' 'unsafe-inline'`.
- **Evidence:** Production HTTP response and source configuration. Other useful directives and headers are present; tested script-looking note text did not execute.
- **Root cause:** Static CSP prioritizes framework compatibility without per-request nonce/hash support.
- **Impact:** CSP provides less defense in depth against a future injection flaw.
- **Recommended fix:** Implement nonce/hash-based Next.js CSP, remove inline script allowance, and test all production hydration/navigation paths.
- **Retest procedure:** Confirm the response has unique nonces or approved hashes, no unsafe inline scripts, no CSP console violations, and no regression across every page.

## Suspected or blocked observations

These are not reported as proven vulnerabilities:

- Python dependency CVE status is unknown because `pip-audit` was not installed.
- Android device-level extraction, backup behavior, and APK network policy were not runtime-tested.
- Google OAuth, n8n, Ollama, and paid/remote AI provider behavior require configured services/credentials.
- A sustained memory-leak, high-concurrency, offline/throttled-network, and large-dataset soak run was not available.
- Supabase failure/recovery and conflict convergence were not deliberately disrupted on the connected external project.
