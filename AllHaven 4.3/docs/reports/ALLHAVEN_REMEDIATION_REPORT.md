# AllHaven — Final Remediation and Clean-State Report

Date: 2026-08-13  
Application: AllHaven 4.2.0  
Final migration head: `0029_ci_email_unique`  
Final workspace state: source-only, ready for a clean installation

## Outcome

All ten findings from the baseline audit were fixed and retested. Additional
security, integrity, resource-exhaustion, synchronization, authentication, and
truthfulness defects discovered during adversarial closure review were also
fixed. The final automated backend suite contains 659 passing tests.

At the owner's request, all AllHaven runtime data was then irreversibly reset
without retaining a backup. Local Docker databases/volumes and the configured
AllHaven Supabase data were emptied, active credentials were removed, and build,
dependency, cache, upload, audit, and backup artifacts were deleted. Source code,
migrations, lockfiles, setup scripts, examples, and audit reports were preserved.

## Baseline finding closure

| ID | Finding | Final status | Closure evidence |
|---|---|---|---|
| ALL-001 | System Control reported healthy containers as stopped | CLOSED | Container-aware probes, truthful unavailable/unknown states, disabled-control actions stripped, and focused runtime/UI tests |
| ALL-002 | Upload limit applied after full allocation | CLOSED | ASGI pre-parser body ceiling, canonical chunked 413 handling, Drive streaming, Knowledge-specific limit, and full-stack regressions |
| ALL-003 | Mobile credentials stored in Preferences | CLOSED | Keychain/Keystore secure storage, write-first migration, plaintext removal, and no insecure fallback |
| ALL-004 | Missing relational integrity | CLOSED | Composite tenant foreign keys, reconciliation migrations, collision-safe upgrades, and cross-workspace rejection tests |
| ALL-005 | Immediate task deletion | CLOSED | Accessible confirmation dialog; cancel preserves and confirm removes the task |
| ALL-006 | Vulnerable frontend dependency graph | CLOSED | Patched dependency graph; complete and production-only npm audits returned zero vulnerabilities |
| ALL-007 | Custom secret encryption | CLOSED | Versioned AES-256-GCM envelopes, context-bound AAD, previous-key reads, and repeatable rotation CLI |
| ALL-008 | Unbounded DOCX expansion | CLOSED | Bounded ZIP/XML extraction, defused XML, parser concurrency cap, plus cumulative structural/decoder budgets for PDF |
| ALL-009 | `127.0.0.1` production-local auth failure | CLOSED | Exact same-port loopback CORS and URL resolution; alternate/hostile origins remain denied |
| ALL-010 | Script CSP allowed `unsafe-inline` | CLOSED | Per-request nonce CSP for web and route-specific script hashes for mobile |

## Additional closure work

- Supabase service-role synchronization is tenant-filtered on fetch and apply.
  Primary-key collisions across workspaces are rejected, pagination uses stable
  `(timestamp, id)` cursors, pull never skips unsent local rows, and remote
  membership/profile ordering is foreign-key safe.
- Configuration/credential ciphertext is excluded from mobile sync.
- RLS reconciliation removes arbitrary legacy policies, keeps secret tables
  inaccessible to clients, refuses email-only profile claims, and normalizes the
  owners of every `SECURITY DEFINER` helper at immutable heads 0026–0027.
- Bearer logout now persists only a SHA-256 revocation identifier and rejects the
  same local or Supabase token immediately. Logout bypasses failed-login rate
  buckets, trusted-proxy client partitioning is explicit, and stale token-verifier
  caching was removed.
- Registration never adopts a profile or remote Auth account by email alone.
  Concurrent registrations map deterministically to 409, email length is bounded,
  missing-account login performs dummy PBKDF2 work, and revision 0029 enforces
  case-insensitive email uniqueness after a collision-safe preflight.
- Session refresh uses an atomic compare-and-swap; one old cookie/CSRF pair can
  produce exactly one new session.
- PDF parsing has per-stream and cumulative decoded-output limits, per-array and
  cumulative structural-item limits, bounded page-tree traversal, cycle/fan-out/
  depth caps, and safe metadata-only fallback. A 3 MB nested-array reproduction
  dropped from about 9.45 seconds / 52.6 MiB to 0.22 seconds / 1.64 MiB.
- Mobile bearer transport fails closed for loopback, malformed/ambiguous IPs, and
  public cleartext HTTP. Cleartext is limited to canonical private RFC1918 or
  Tailscale bridges; public backends require HTTPS.
- Supabase Connect, System Control, and logout UIs no longer display success when
  the corresponding backend operation failed or was disabled.

## Final verification before clean reset

| Check | Result |
|---|---|
| Backend suite | **659 passed** |
| Installer suite | **18 passed** |
| Frontend policy/security tests | **22 passed** after final auth changes |
| TypeScript | PASS |
| Desktop production build | PASS during integrated remediation |
| Mobile static build | PASS; 20 HTML files hardened with 340 script hashes |
| Capacitor sync/plugins | PASS; secure-storage and Preferences registered |
| npm audit (complete and production-only) | 0 vulnerabilities |
| Python `pip-audit` | No known vulnerabilities |
| Fresh SQLite migration | PASS to `0029_ci_email_unique` |
| PostgreSQL 16 migration | PASS to `0029_ci_email_unique`; both CI email indexes enforced |
| Focused PostgreSQL collision upgrade | Safe abort at 0028; rows preserved; no partial indexes |
| Production/local Compose render | PASS |
| Diff whitespace validation | PASS |

One Starlette TestClient deprecation warning remains in the test environment; it
does not fail the suite or affect the deployed ASGI runtime.

## Runtime evidence captured before reset

- System Control converged to Backend, Frontend, and PostgreSQL running with no
  contradictory banner.
- Runtime CORS accepted `localhost:3000` and `127.0.0.1:3000`, while rejecting an
  alternate port and an untrusted origin.
- Runtime CSP nonced every script tag, used `strict-dynamic`, contained no
  `unsafe-inline` in `script-src`, and generated a different nonce per response.
- Fixed-length and chunked oversize upload probes returned canonical 413 errors.
- Browser tests covered both loopback hostnames and task delete cancel/confirm.

This evidence is historical: the application stack was intentionally removed in
the clean-state reset below.

## Clean-state reset verification

- Local Compose projects named AllHaven: **0**
- AllHaven containers, networks, application images, and data volumes: **0**
- Local database/dump artifacts in the workspace: **0**
- Retained database backups: **0**
- Active `.env`, `.env.prod`, backend/frontend environment files: **0**
- AllHaven Supabase application rows sampled across identity/business tables: **0**
- Supabase Auth users: **0**
- Supabase Storage buckets: **0**
- Local uploads, audit databases, test accounts, sessions, build outputs,
  `node_modules`, Python virtual environment, and test/browser caches: removed
- No separate Windows AllHaven installation, shortcut, or user-data directory was
  found outside the workspace.

The shared `postgres:16` base image and global Docker BuildKit cache were not
removed because they are not exclusively AllHaven data. Ollama was also left
untouched; it is a separate installed application and currently has no models.

## Preserved for the next installation

- Application source and migration history through revision 0029
- `package-lock.json`, requirements/pyproject manifests, and Android source
- `.env.example`, `.env.prod.example`, and frontend environment example
- Setup/install scripts and Docker Compose definitions
- Audit and remediation reports

## Remaining platform verification limits

- APK assembly and physical Android secure-storage inspection require a JDK/
  Android Studio and a device; this host did not provide them.
- iOS Keychain/device verification requires macOS and an iOS device.
- Live Google OAuth, n8n, paid AI providers, externally hosted TLS, and deliberate
  third-party outage tests require newly configured real services/credentials.

## Final disposition

No concrete reproducible blocker remains in the audited code scope. The workspace
is deliberately not running and contains no retained AllHaven user database. The
next installer run should create new credentials, dependencies, images, schema,
volumes, and the first user as a clean installation.
