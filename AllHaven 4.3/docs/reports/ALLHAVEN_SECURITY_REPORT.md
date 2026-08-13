# AllHaven Security Report

> Historical baseline assessment. The listed application findings were remediated;
> see `ALLHAVEN_REMEDIATION_REPORT.md` for current security and retest evidence.

Audit date: 2026-08-13. This is a non-destructive baseline assessment; no exploit payload intended to exhaust resources and no application fix was executed.

## Overall assessment

**Security score: 60/100.** No authentication bypass, cross-workspace IDOR, reflected/stored XSS execution, committed live secret, or exposed production API documentation was confirmed. The main blockers are two authenticated denial-of-service paths evident in upload processing, insecure mobile credential persistence, a custom production cryptographic construction, and outdated frontend dependencies.

## CRITICAL

No confirmed critical finding.

## HIGH

### ALL-002 — Full upload is allocated before the size limit

Authenticated Drive and Knowledge uploads are read completely with `await file.read()` before the configured limit is checked. This can turn a nominal validation control into worker memory exhaustion. See `ALLHAVEN_FINDINGS.md` for source trace and retest limits.

### ALL-003 — Mobile credentials are stored in Capacitor Preferences

Bearer and Supabase session values are persisted in storage backed by Android SharedPreferences/iOS UserDefaults rather than a Keystore/Keychain credential store. Capacitor's storage description: https://capacitorjs.com/docs/apis/preferences

## MEDIUM

### ALL-006 — Four high npm production-package findings

`npm audit --omit=dev` found high findings in the installed `next`, `postcss`, `nanoid`, and `sharp` graph. Several current exploit prerequisites were not found (no Server Actions, rewrites, or runtime attacker-controlled CSS processing), so the application-level severity is assessed MEDIUM rather than blindly copying the scanner label. Patch and regression testing remain required.

### ALL-007 — Custom MVP secret encryption remains in production

Integration secrets are not plaintext and have an HMAC integrity check, but confidentiality uses a custom SHA-256 keystream/XOR construction. Replace with a reviewed AEAD/KMS solution and a versioned rotation/migration strategy.

### ALL-008 — DOCX decompression budget is unbounded

Knowledge extraction reads selected ZIP entries without an entry/cumulative uncompressed-size or compression-ratio cap. This is a second authenticated availability risk, independent of compressed request size.

### ALL-009 — Loopback-origin CORS mismatch

Hostile origins were rejected correctly, but the application is exposed on `127.0.0.1:3000` while that origin is not allowed. This is primarily functional, not a permissive-CORS vulnerability.

## LOW

### ALL-010 — CSP permits inline scripts

Production CSP includes `script-src 'self' 'unsafe-inline'`. Frame, object, base, referrer, MIME-sniff, permissions, and framing protections were otherwise present. Use nonce/hash-based script policy for stronger defense in depth.

## INFO / hardening observations

- Frontend responses disclose `X-Powered-By: Next.js`.
- HSTS was not present on the local HTTP target; HSTS must be verified at the real HTTPS termination point before release.
- The backend test suite emitted an httpx/Starlette TestClient deprecation warning; this is maintenance risk, not a security defect.
- Only one database foreign key exists. That is tracked as high data-integrity finding ALL-004, not an access-control bypass.

## Controls that were proven

| Control | Evidence | Result |
|---|---|---|
| Anonymous access denial | Protected data endpoints returned 401 | PASS |
| Workspace isolation / IDOR | Second user could not read/update/delete first user's tasks, notes, finance, events, automations, memory, AI sessions, Drive files, or Knowledge documents | PASS |
| CSRF | HttpOnly cookie session plus readable CSRF token/header validation in state-changing dependencies and tests | PASS |
| CORS hostile-origin rejection | Arbitrary hostile Origin preflight rejected with no allow-origin | PASS |
| XSS baseline | Script-looking task/note values stored and rendered as inert text; no console execution | PASS for tested sinks |
| Path traversal baseline | Drive upload reduced traversal-looking filename to safe basename; workspace storage path containment exists | PASS |
| API schema/docs production exposure | `/docs`, `/redoc`, `/openapi.json` all 404 | PASS |
| Secret disclosure | No tracked live `.env`/private key; settings responses mask secret values | PASS |
| Weak production config | Weak secrets rejected during settings validation | PASS |
| Download ownership | Cross-workspace Drive/Knowledge access returned 404 | PASS |

## Blocked security coverage

- Python package vulnerability scan: `pip-audit` unavailable.
- Mobile APK/device: no emulator/device for backup/file extraction, TLS, exported-component, or WebView inspection.
- Live Google, n8n, Ollama, and external AI provider security: services/credentials unavailable.
- High-volume concurrency, resource exhaustion, long soak, and deliberate Supabase outage tests were not performed.
- HTTPS edge controls (HSTS, certificate, TLS versions/ciphers) require the actual external endpoint.

## Release gate

Before production or trusted daily use, close ALL-002, ALL-003, ALL-004, and ALL-008; upgrade the vulnerable frontend dependency graph; replace/migrate custom secret encryption; and run the blocked device, Python dependency, external edge, and resource-limit tests.
