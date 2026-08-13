# AllHaven Retest Plan

> This was the baseline retest plan. Its application-level closure checks were
> executed during remediation; results are in `ALLHAVEN_REMEDIATION_REPORT.md`.

Baseline date: 2026-08-13. No fixes were applied during the audit, so every finding below is **OPEN / NOT RETESTED**. This plan defines proof required to close them.

## Entry criteria

1. Record the commit, container image digests, dependency lockfiles, environment profile, and migration head.
2. Use an isolated copy of production-like PostgreSQL/Supabase data with recoverable backups.
3. Configure resource monitoring for backend RSS/CPU, request duration, container restarts, DB constraint errors, and browser console/network logs.
4. Create two ordinary users and one non-owner/unauthenticated context; do not use administrator credentials for tenant-isolation tests.
5. Redact cookies, bearer tokens, provider keys, and Supabase credentials from evidence.

## Finding retests

| Finding | Required retest | Pass criteria |
|---|---|---|
| ALL-001 | Compare System Control API/UI with Docker ground truth while frontend, backend, DB, and optional agent are individually running, stopped, restarting, and unreachable | Every state is correct; unobservable is `unknown`; banner/counters agree; no false success/failure |
| ALL-002 | Upload below, at, above, and far above limit using fixed-length and chunked bodies; run concurrent attempts while monitoring RSS | Oversized request rejected early (413/validated equivalent); RSS does not scale with full body; no partial file/row remains |
| ALL-003 | Build/install Android and iOS targets; inspect app storage and eligible backups before/after login/logout/revocation | No bearer/refresh/session credential in Preferences/plain files/backups; Keychain/Keystore used; logout/revocation removes access |
| ALL-004 | Query full FK inventory; insert invalid parent IDs; delete every parent class; run orphan checks; migrate a production-like copy forward/back as supported | All logical relationships constrained intentionally, indexes exist, delete behavior documented, no orphan/data loss |
| ALL-005 | Delete a task via mouse, keyboard, double-click, slow network, and two tabs; cancel and undo | Accidental activation cannot permanently delete; cancel is safe; duplicate request is idempotent; recovery works |
| ALL-006 | Upgrade dependencies, run `npm audit --omit=dev`, build, and exercise App Router, cache, images, headers, and all pages | Zero high/critical production findings and no functional regression |
| ALL-007 | Test versioned encryption, tamper/wrong-key handling, key rotation, legacy migration, backup restore, and masking/logging | Vetted AEAD/KMS used; safe rotation and rollback plan proven; no plaintext/log/API disclosure |
| ALL-008 | Upload normal/corrupt/high-ratio/many-entry/oversized-entry DOCX files concurrently while monitoring RSS/CPU | Suspicious archive rejected before large expansion; normal documents index correctly; no leftover rows/files |
| ALL-009 | Test localhost, IPv4/IPv6 loopback, intended LAN/Tailscale origins, Capacitor origins, and hostile origins through register/login/logout/CSRF | Intended origins work or canonicalize; hostile origins remain denied; cookie/CSRF behavior is consistent |
| ALL-010 | Inspect production CSP and browser console across all routes after nonce/hash migration; try controlled inline script sink | No blanket inline-script allowance, unique/valid nonces or hashes, no hydration/navigation break, controlled sink blocked |

## Mandatory regression suite

- Frontend production build and all 17 page-route smoke tests.
- All 586 backend tests and 18 installer tests, plus new regression coverage for every fixed finding.
- Compose config validation for base, local, production HTTPS, and production-local variants.
- Registration/login/logout/refresh, expired/revoked session, CSRF, CORS, invalid UUID, and anonymous access.
- Two-user IDOR suite for tasks, checklist items, notes, finance/categories, events, automations, AI sessions/groups/memory/proposals, Drive, Knowledge, settings, and system controls.
- Full CRUD and refresh/persistence for tasks, notes, finance, routines, automations, memory, Drive, and Knowledge.
- Multi-tab create/update/delete/undo and stale-state recovery.
- Mobile widths 320/375/430, tablet 768, desktop 1024/1440+, keyboard focus, modal focus trap, labels, and screen-reader sampling.
- Database backup/restore, migration, orphan checks, constraint checks, and Supabase sync conflict/outage recovery.
- Google OAuth, n8n, Ollama, and each supported AI provider using dedicated non-production credentials.
- Sustained soak, concurrent uploads/mutations, offline/throttled network, backend/DB/provider outage, and recovery.
- Python and frontend dependency scans plus container/image and secret scans.

## Evidence package for closure

For each finding, retain the exact build/commit, sanitized request/response, UI capture when relevant, backend log, database query, resource graph, and the new automated regression test. A green toast or HTTP 200 without resulting-state proof is insufficient.

## Exit criteria

- No open HIGH issue.
- No known false operational/business signal.
- No cross-workspace access or secret exposure.
- Upload/resource limits proven under adversarial and concurrent inputs.
- Database relationship integrity and migration safety proven.
- All blocked external/mobile/dependency coverage completed.
- Full regression suite passes twice: once on a fresh deployment and once on an upgraded production-like deployment.
