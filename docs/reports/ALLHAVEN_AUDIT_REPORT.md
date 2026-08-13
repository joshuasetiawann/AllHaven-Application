# ALLHAVEN COMPLETE AUDIT

> Historical baseline: this document records the application before remediation.
> The findings have since been fixed and retested. See
> `ALLHAVEN_REMEDIATION_REPORT.md` for the final implementation and evidence.

Audit baseline: 2026-08-13  
Target: current dirty working tree plus production-local Docker deployment  
Method: repository discovery, build/test execution, browser/UI workflows, API/authorization tests, database inspection, container truth comparison, and security review  
Change policy: **audit only—no source, configuration, schema, or dependency fix was applied**

## Executive Summary

AllHaven is a substantial personal productivity application, not merely an AI demo. Its core local workflows—authentication, tasks/checklists, notes, finance, routines/calendar, automations, memory, Drive, Knowledge, responsive navigation, and workspace authorization—mostly work end to end. Important successes were validated beyond the UI: records were read back, summaries checked, second-user access denied, bytes downloaded, searches re-run, delete state confirmed, sessions refreshed, and multi-tab state observed.

It is not yet trustworthy enough for production or unsupervised daily use. The System Control screen gives false container status in the tested Docker deployment; two authenticated file paths can allocate/decompress unbounded data; mobile bearer/session credentials use ordinary Preferences storage; and the database delegates nearly all referential integrity to application code. Task deletion also lacks a recovery interlock, the frontend dependency audit is not clean, production secret encryption is a custom MVP construction, one common loopback URL breaks at CORS, and CSP permits inline scripts.

The existing automated tests are strong but not sufficient as release proof: **586 backend tests passed**, **18 installer tests passed**, and the frontend production build passed, yet runtime and schema inspection still found the issues above.

- **Functional Reliability: 81/100**
- **Data Integrity: 64/100**
- **Security: 60/100**
- **UX Reliability: 77/100**
- **Production Readiness: 58/100**

### Test result summary

| Total | PASS | FAIL | PARTIAL | BLOCKED | FAKE SIGNAL | SECURITY ISSUE |
|---:|---:|---:|---:|---:|---:|---:|
| 72 | 49 | 2 | 6 | 9 | 1 | 5 |

### What genuinely works

- Canonical localhost registration/login, cookie session restore, reload, back/forward, logout, and multi-tab authentication.
- Tasks and checklist mutations, state transitions, notes/tags, finance arithmetic/validation, calendar timezone/repeat validation, automations, and AI memory.
- Local Drive file round-trip and safe basename handling; Knowledge text indexing/search/reindex/delete.
- Workspace isolation across all tested major resources. Anonymous protected access is denied.
- Production build, migrations, Docker stack, health endpoint, production docs suppression, hostile-origin CORS rejection, CSRF model, and several security headers.
- Honest unavailable signals for unconfigured AI and n8n paths—no fabricated answer/workflow was observed.
- Representative pages at mobile through wide desktop widths, with a usable mobile navigation drawer and no global horizontal overflow.

### What does not yet work safely

- System Control cannot truthfully observe sibling Docker containers and contradicts its own status summary.
- Upload limits are applied after full request allocation; DOCX expanded data is unbounded.
- Mobile credentials are not stored in a platform credential vault.
- Core relational ownership/dependency rules lack database foreign keys.
- One-click task deletion is irreversible from the UI.
- `127.0.0.1` can render the frontend but cannot authenticate because production-local CORS only includes `localhost`.
- Live Google, n8n, Ollama, external AI providers, APK/device behavior, full Supabase outage/conflict behavior, Python CVE scanning, clean blank-host install, and sustained load/soak remain blocked.

# FEATURE RESULTS

The canonical detailed mapping is `ALLHAVEN_FEATURE_INVENTORY.md`. Every discovered reachable feature is listed below; `PASS` never means an unconfigured external provider was assumed to work.

| ID | Feature | Result |
|---|---|---|
| F-001 | Root landing/authenticated redirect | PASS |
| F-002 | Registration/login | PASS on localhost; FAIL on 127 alias |
| F-003 | Session restore/refresh | PASS |
| F-004 | Logout/profile update | PASS |
| F-005 | Dashboard overview/counts | PASS for tested data |
| F-006 | Sidebar/mobile drawer/modules/command navigation | PASS |
| F-007 | Task CRUD | PARTIAL: CRUD works, deletion safety does not |
| F-008 | Task checklist | PASS |
| F-009 | Complete/reopen task transitions | PASS |
| F-010 | Notes/tags CRUD | PASS |
| F-011 | Finance categories | PASS by API/source; UI route loads |
| F-012 | Finance transaction CRUD/filter/validation | PASS |
| F-013 | Finance summary/report | PASS for tested arithmetic |
| F-014 | Routine/event CRUD | PASS |
| F-015 | Routine batch/generation/sync | PARTIAL / provider paths BLOCKED |
| F-016 | Calendar compatibility route/API | PASS; intentional route redirect |
| F-017 | Drive config/list | PASS |
| F-018 | Drive upload/download/delete | PASS for normal file; SECURITY ISSUE in limit enforcement |
| F-019 | Single-provider AI chat | PARTIAL; honest no-provider behavior proven |
| F-020 | AI groups/sessions/messages | PASS for tested CRUD/isolation |
| F-021 | Multi-agent chat | BLOCKED |
| F-022 | Debate mode | BLOCKED |
| F-023 | Reasoning mode | BLOCKED |
| F-024 | Agent run inspection | BLOCKED beyond source/tests |
| F-025 | Tool proposals/approval | PARTIAL; real provider proposal BLOCKED |
| F-026 | AI tool registry/enablement | PARTIAL; destructive execution not exercised |
| F-027 | AI policy/chat settings | PASS by source/tests; route loads |
| F-028 | Provider config/slots/test/enable | PARTIAL; live providers BLOCKED |
| F-029 | Knowledge document CRUD | PASS for text; SECURITY ISSUE in resource limits |
| F-030 | Knowledge index/search/reindex | PASS |
| F-031 | AI memory CRUD/enable/disable | PASS |
| F-032 | Memory search/settings/suggestions/Supabase sync | PARTIAL |
| F-033 | Automation CRUD | PASS |
| F-034 | n8n workflows/activation | BLOCKED, honestly reported |
| F-035 | Approval review UI | PARTIAL |
| F-036 | Profile/preferences/privacy settings | PARTIAL |
| F-037 | Integration configuration lifecycle | PARTIAL |
| F-038 | Google OAuth/Calendar connection | BLOCKED |
| F-039 | Supabase connection/sync status | PARTIAL |
| F-040 | System health dashboard | FAKE SIGNAL |
| F-041 | System controls/logs/ports | BLOCKED without Haven Agent |
| F-042 | Calculator | PASS route/basic smoke |
| F-043 | Clock/timer | PASS route/basic smoke |
| F-044 | Notifications control | PARTIAL; no delivery service discovered |
| F-045 | Responsive shell | PASS on sampled routes and six widths |
| F-046 | Cookie/CSRF/CORS/workspace security boundary | PARTIAL due CORS defect; isolation/CSRF pass |
| F-047 | PostgreSQL/Alembic | PARTIAL due missing foreign keys |
| F-048 | Local-first Supabase background sync | PARTIAL |
| F-049 | Docker/startup/installer | PASS for current host; clean host BLOCKED |
| F-050 | Capacitor Android auth/data mode | SECURITY ISSUE; device runtime BLOCKED |
| F-051 | Health/version/deployment profile | PASS |
| F-052 | Production headers/docs exposure | PARTIAL due weak script CSP |

# FAKE SIGNAL REPORT

**Did AllHaven ever tell the user something succeeded when it actually did not?**

No false-success business action was confirmed. Task, note, finance, calendar, automation, memory, Drive, and Knowledge success paths were checked against resulting API/database/file state. AI without a provider and n8n without configuration reported limitations honestly.

However, AllHaven did present a confirmed false operational state: System Control said Frontend and PostgreSQL were stopped even though Docker showed both running (PostgreSQL healthy), then simultaneously said `No services need attention`. This is ALL-001 and is a production-readiness blocker. Full evidence is in `ALLHAVEN_FAKE_SIGNAL_REPORT.md`.

# SECURITY REPORT

Ordered by severity:

## CRITICAL

None confirmed.

## HIGH

1. **ALL-002:** Drive/Knowledge upload bodies are fully read into memory before the size check.
2. **ALL-003:** Mobile bearer/Supabase sessions are persisted in Capacitor Preferences rather than Keychain/Keystore-backed storage.
3. **ALL-004:** Only one foreign key exists across the public schema, leaving core relational integrity unenforced. This is primarily data integrity but materially affects secure tenant/data lifecycle behavior.

ALL-001 is also HIGH but categorized as Fake Signal/Reliability.

## MEDIUM

1. **ALL-006:** Four high findings in the production npm package graph; current source reduces several advisory preconditions but remains on affected ranges.
2. **ALL-007:** Integration secrets use a custom, self-described MVP SHA-256 keystream/HMAC construction.
3. **ALL-008:** DOCX ZIP expansion has no uncompressed-size/compression-ratio budget.
4. **ALL-009:** Production-local CORS rejects the exposed IPv4 loopback alias.

ALL-005 (unsafe task deletion) is also MEDIUM but categorized as UX/Data Integrity.

## LOW

1. **ALL-010:** CSP permits inline scripts, reducing XSS defense in depth.

## INFO

- `X-Powered-By: Next.js` is exposed.
- HSTS must be verified at the real HTTPS edge; the local HTTP target cannot prove it.
- Python dependency CVE status is blocked because `pip-audit` is not installed.

Detailed threat coverage, proven controls, and blocked coverage are in `ALLHAVEN_SECURITY_REPORT.md`.

# TOP 10 MOST IMPORTANT ISSUES

1. **ALL-001 / HIGH — Fake system health:** the operations screen cannot be trusted in the tested Docker deployment.
2. **ALL-002 / HIGH — Upload memory exhaustion:** nominal size limits do not prevent full-body allocation.
3. **ALL-003 / HIGH — Mobile credential storage:** reusable credentials are stored outside a platform vault.
4. **ALL-004 / HIGH — Missing database relationships:** most corruption/orphan prevention depends only on perfect application behavior.
5. **ALL-008 / MEDIUM — DOCX decompression exhaustion:** compressed uploads can expand without a budget.
6. **ALL-005 / MEDIUM — One-click permanent task deletion:** realistic accidental data-loss path.
7. **ALL-006 / MEDIUM — Vulnerable dependency ranges:** production lock graph contains four high audit findings.
8. **ALL-007 / MEDIUM — Custom cryptography:** an MVP construction remains responsible for production integration secrets.
9. **ALL-009 / MEDIUM — Local-origin split-brain:** a URL that renders successfully cannot use authentication/API.
10. **ALL-010 / LOW — Inline-script CSP:** weaker containment if another injection issue appears.

# FIX PRIORITIES

## P0

No confirmed active breach or current data-loss incident requiring emergency intervention. If AllHaven is already Internet-exposed or distributed as a production mobile APK, treat ALL-002/003/008 as immediate release-stopping work.

## P1

- Correct System Control truth semantics (ALL-001).
- Enforce streaming/proxy upload caps and DOCX expansion budgets (ALL-002, ALL-008).
- Move mobile credentials to Keystore/Keychain storage and validate revocation (ALL-003).
- Design, validate, and migrate core foreign keys without losing existing data (ALL-004).
- Replace custom secret encryption with versioned vetted AEAD/KMS and rotation (ALL-007).
- Upgrade affected production frontend dependencies and run regression coverage (ALL-006).

## P2

- Add confirmation plus recoverable deletion/undo for tasks (ALL-005).
- Canonicalize or correctly allow intended local origins while keeping hostile origins denied (ALL-009).
- Complete blocked Google/n8n/Ollama/AI/Supabase outage tests.
- Run Python dependency, mobile device, HTTPS edge, concurrent-load, and long-soak assessments.

## P3

- Replace inline-script CSP with nonce/hash policy and remove technology disclosure (ALL-010).
- Complete WCAG/screen-reader and large-dataset performance audits.
- Remove the backend test-client deprecation warning before it becomes a test-infrastructure break.

# FINAL REAL-WORLD TEST

A realistic session was performed rather than isolated button checks:

1. Registered through the canonical local URL and verified a workspace/session was provisioned.
2. Navigated the authenticated dashboard and all discovered page routes with console monitoring.
3. Created a task from the actual UI, opened a second tab, and proved the second tab shared authentication and saw the new task.
4. Used browser back/forward and reloaded an authenticated route; state and session remained consistent.
5. Exercised task/checklist lifecycle, notes/tags, finance summary, routine/calendar timezone validation, automation, memory/search, AI session/no-provider behavior, Drive byte round-trip, and Knowledge indexing/search/reindex through API-backed workflows.
6. Repeated ownership operations as a second user and confirmed 404/denial rather than cross-workspace data access.
7. Compared health/status claims with actual container/database state.
8. Removed all audit-created data afterward. Nine local and nine matching Supabase Auth audit accounts plus their audit workspaces/data were deleted; verification found zero matching accounts and no representative orphan rows.

The core productivity workflow stayed consistent during this session. The decisive failures were operational truth, data-safety interlocks, and security/design boundaries rather than a broadly broken CRUD application.

# LIMITATIONS AND BLOCKED AREAS

- External credentials/services were not invented or used: Google OAuth, n8n, Ollama, and real AI provider calls remain blocked.
- No Android/iOS device or emulator was available for APK install, file extraction, backup, TLS, WebView, and lifecycle testing.
- `pip-audit` was unavailable, so Python dependencies were not assigned a clean security result.
- A clean blank host was not available; Compose variants, builds, migrations, running containers, and installer tests were validated instead.
- No destructive archive bomb, multi-gigabyte upload, sustained concurrency attack, or third-party Supabase outage was launched. Those risks are reported as high-confidence code issues or partial/blocked tests.
- No sufficiently long browser/process profiling window was available for a memory-leak soak.
- The repository was already heavily modified. Those user changes were preserved; only the requested audit artifacts were added.

# FINAL QUESTION

> If I used AllHaven every day and trusted it with my real information, would I currently trust it not to lose data, lie about successful operations, expose information, or unexpectedly break?

**NO.** The tested core workflows are substantially real, but the false System Control state, immediate irreversible deletion, missing database constraints, upload/decompression availability risks, insecure mobile credential persistence, and incomplete external/mobile/load coverage leave too much uncertainty for trusted daily or production use. The application is suitable for controlled testing while the P1 findings are addressed and independently retested.

# FINAL VERDICT

**SAFE FOR TESTING ONLY**
