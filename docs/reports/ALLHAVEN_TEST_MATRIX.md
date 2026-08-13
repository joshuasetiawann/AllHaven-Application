# AllHaven Test Matrix

Execution window: 2026-08-12 to 2026-08-13 (Asia/Jakarta). Runtime target: production-local Docker stack at `http://localhost:3000` and `http://localhost:8000`.

Result totals: **72 tests — 49 PASS, 2 FAIL, 6 PARTIAL, 9 BLOCKED, 1 FAKE SIGNAL, 5 SECURITY ISSUE**.

| ID | Feature | Test | Expected | Actual / evidence | Result |
|---|---|---|---|---|---|
| T-001 | Frontend | Production Next.js build | Build completes | `npm run build` completed; 22 routes generated | PASS |
| T-002 | Backend | Automated test suite | Tests pass | 586 tests collected and passed; one deprecation warning | PASS |
| T-003 | Installer | Installer tests | Tests pass | 18 tests passed | PASS |
| T-004 | Compose | Base Compose validation | Valid configuration | `docker compose config` exit 0 | PASS |
| T-005 | Compose | Local Compose validation | Valid configuration | Local override config exit 0 | PASS |
| T-006 | Compose | Production/HTTPS and production-local validation | Valid configurations | Both resolved successfully | PASS |
| T-007 | Configuration | Production with weak secrets | Fail closed | Settings validation rejected weak production secrets | PASS |
| T-008 | Database | Migration state | At current head | `alembic_version=0020_ai_memory_soft_delete` | PASS |
| T-009 | Startup | Container health | Frontend/backend/DB running | Three production-local containers up; DB healthy | PASS |
| T-010 | Health | Backend health semantics | Real status and profile | 200 with status `ok`, version 4.2.0, production/private/local DB | PASS |
| T-011 | Production exposure | Swagger/OpenAPI/Redoc | Disabled in production | `/docs`, `/openapi.json`, `/redoc` returned 404 | PASS |
| T-012 | Entry/Auth | Root and login direct navigation | Pages render | Rendered with no console errors | PASS |
| T-013 | Registration | Register at canonical `localhost` | Account/workspace/session created | UI registration succeeded and dashboard loaded | PASS |
| T-014 | Registration/CORS | Register at `127.0.0.1:3000` | Supported local alias should call API | Preflight returned 400; UI reported API unreachable | FAIL |
| T-015 | Auth | Login/logout/session handling | Correct session transitions | Cookie session and logout paths passed in UI/API/test suite | PASS |
| T-016 | Auth | Refresh/reload authenticated page | Session persists | Reload of Notes remained authenticated | PASS |
| T-017 | Navigation | Browser back/forward | Correct history state | Tasks → Notes → back/forward returned correct routes | PASS |
| T-018 | Routing | Invalid URL | Honest 404 | Next.js 404 rendered | PASS |
| T-019 | Authorization | Direct unauthenticated dashboard/API access | Redirect/401 | Protected UI/API denied anonymous access | PASS |
| T-020 | State | Multi-tab auth and data | Shared session and current state | Second tab authenticated and saw newly created task | PASS |
| T-021 | Routes | Smoke all discovered pages | Each route loads or intentionally redirects | 17 page routes loaded; Calendar intentionally redirected to Routine | PASS |
| T-022 | Browser | Console/runtime errors during route smoke | No JS/React/hydration error | No persistent warning/error found | PASS |
| T-023 | Responsive | Representative pages at 320–1440 px | No global horizontal overflow; nav usable | Dashboard/Tasks/Finance/Settings passed; mobile drawer usable | PASS |
| T-024 | Responsive | Wide desktop shell | Stable layout | 1440 px view usable, no global overflow | PASS |
| T-025 | Tasks | Create/read with special title and leap-date timezone | Persist exact safe data | Stored as text; date normalized from +07 to UTC | PASS |
| T-026 | Tasks | Update, complete, reopen | Correct state/timestamps | TODO/DONE/TODO transitions persisted | PASS |
| T-027 | Tasks | Checklist add/update/delete | Correct item state | Trimmed values and mutations persisted | PASS |
| T-028 | Tasks | Delete and post-delete read | Resource removed | Delete succeeded; subsequent GET 404 | PASS |
| T-029 | Tasks | Accidental-delete protection | Confirmation or undo before irreversible removal | Delete icon removed task immediately; no confirmation/undo | FAIL |
| T-030 | Notes | CRUD, tags, refresh-level persistence | Correct stored values | Create/read/update/delete passed; tags trimmed/deduplicated | PASS |
| T-031 | Notes/XSS | Script-looking title/content | Render/store as text | Payload remained inert text; no browser execution observed | PASS |
| T-032 | Finance | Transaction CRUD, decimal, lowercase currency | Exact arithmetic and normalization | `12345.67`; currency normalized to IDR | PASS |
| T-033 | Finance | Invalid negative amount | Reject | Returned 422 | PASS |
| T-034 | Finance | Summary aggregation | Exact totals/count | Income/balance/count matched database action | PASS |
| T-035 | Routine/Calendar | Event CRUD, repeat-day validation, timezone | Persist/normalize; reject invalid day | UTC normalization correct; invalid `night` returned 422 | PASS |
| T-036 | Automations | Create/update/delete | Persist mutations | CRUD passed | PASS |
| T-037 | Calendar API | Cross-user event mutation | Deny as not found | Other user received 404 | PASS |
| T-038 | Memory | CRUD/search/enable/disable | Correct state and ownership | All tested actions persisted | PASS |
| T-039 | AI | Group/session creation and isolation | Persist and scope | Own session worked; other user received 404 | PASS |
| T-040 | AI | Chat without configured provider | Honest unavailable state | Response explicitly set `ai_configured:false`; no fake answer | PASS |
| T-041 | Drive | Upload/list/download/delete | Full chain and bytes match | Small text file round-trip matched 909 bytes; delete then 404 | PASS |
| T-042 | Drive | Traversal-style filename | Store safe basename | `../../audit-license.txt` became `audit-license.txt` | PASS |
| T-043 | Drive | Cross-workspace download | Deny | Other user received 404 | PASS |
| T-044 | Knowledge | Upload/index/search/reindex/delete | Full chain | One chunk indexed; search found content; reindex/delete passed | PASS |
| T-045 | Knowledge | Cross-workspace document read | Deny | Other user received 404 | PASS |
| T-046 | IDOR | Other-user read/update/delete across resources | Deny all | Tasks, notes, finance, events, automations, memory, AI, Drive, Knowledge denied | PASS |
| T-047 | Auth boundary | Anonymous data endpoints | 401 | Returned 401 | PASS |
| T-048 | API validation | Invalid UUID | Structured client error | Returned 422; unknown valid ID returned 404 | PASS |
| T-049 | CORS | Evil origin vs canonical trusted origins | Reject evil, allow configured | Evil rejected; localhost/Capacitor configured origins allowed | PASS |
| T-050 | CSRF | Cookie state-change protection | Require CSRF header | Middleware/source/test suite enforce token/header match | PASS |
| T-051 | Secrets | Tracked-file/private-key scan and API masking | No committed secret disclosure | No tracked live env/private key found; integration secrets masked | PASS |
| T-052 | Headers | Production security headers/CSP | Strong headers without unsafe script policy | XFO/nosniff/referrer/permissions present; CSP has `script-src 'unsafe-inline'` | PARTIAL |
| T-053 | Database | Referential-integrity constraints | Key relationships enforced by DB | Only one foreign key exists across public schema | PARTIAL |
| T-054 | System status | UI health vs actual Docker state | Exact operational truth | UI showed Frontend/PostgreSQL stopped while both containers were up; also said no attention needed | FAKE SIGNAL |
| T-055 | Mobile security | Bearer/session token at-rest storage | OS keystore-backed secure storage | Capacitor Preferences/SharedPreferences/UserDefaults used | SECURITY ISSUE |
| T-056 | Upload security | Enforce body size before allocation | Stream/reject before full read | Routers call `await file.read()` before 250 MB check | SECURITY ISSUE |
| T-057 | Knowledge security | Bound DOCX decompression | Reject excessive expanded archive | XML entries read without expanded-size/ratio cap | SECURITY ISSUE |
| T-058 | Dependencies | Frontend production dependency audit | No known high advisories | `npm audit --omit=dev`: 4 high package findings | SECURITY ISSUE |
| T-059 | Secret crypto | Standard vetted authenticated encryption | Supported primitive/KMS | Production service uses custom SHA-256 keystream + HMAC scheme documented as MVP | SECURITY ISSUE |
| T-060 | Dependencies | Python CVE audit | Scan installed dependency graph | `pip-audit` unavailable in environment; no install performed | BLOCKED |
| T-061 | Google | OAuth login/calendar sync live flow | Complete consent/callback/sync | No Google credentials or consent session | BLOCKED |
| T-062 | n8n | Live workflow list/activation | Real n8n mutation | n8n not configured | BLOCKED |
| T-063 | External AI | OpenAI/Anthropic/Gemini/Grok/OpenRouter calls | Real provider response | Provider credentials/configuration unavailable for safe live calls | BLOCKED |
| T-064 | Ollama | Local model call | Real model response | Ollama unavailable/unconfigured | BLOCKED |
| T-065 | Android | Installed APK cold start/auth/storage inspection | Device-level proof | No emulator/device/install target available | BLOCKED |
| T-066 | Network | Throttled/offline/recovery matrix | Stable retry and honest errors | Only local alias/API-unreachable behavior exercised; systematic throttling unavailable | BLOCKED |
| T-067 | Performance | Sustained memory-leak/soak test | Stable long session | No sufficiently long profiling window/tooling | BLOCKED |
| T-068 | Installation | Blank-host clean install | Reproducible from zero state | Builds/configs validated, but current dirty workspace and existing Docker host are not a clean host | BLOCKED |
| T-069 | Supabase | Registration mirror and sync behavior | Local/remote identity and rows align | Audit identities mirrored and background `sync_state` rows observed; outage/conflict recovery not tested | PARTIAL |
| T-070 | Background sync | Worker health, interval, failure recovery | Honest status and convergence | 15-second interval reported and sync rows created; deliberate third-party outage not induced | PARTIAL |
| T-071 | Accessibility | Labels, keyboard-reachable primary controls, mobile menu | Basic operability | Semantic names present in sampled screens; no full WCAG/screen-reader audit | PARTIAL |
| T-072 | Performance | Page responsiveness and large-data behavior | Acceptable under realistic load | Small-data route interactions responsive; large-volume/load test not performed | PARTIAL |

## Data cleanup

All nine local audit accounts and nine matching Supabase Auth audit accounts used for these tests were removed after execution, together with their audit workspaces and dependent test rows. Post-cleanup checks returned zero matching audit accounts and zero orphans for profiles, workspace owners, and representative workspace-owned resources.
