# AllHaven Feature Inventory

Audit baseline: 2026-08-13. Discovery sources: Next.js pages and components, FastAPI routers/services, SQLAlchemy models and Alembic migrations, Docker/installer configuration, documentation, and the running production-local stack.

Status in this inventory is the audit disposition, not merely whether a screen exists. Detailed evidence is in `ALLHAVEN_TEST_MATRIX.md` and `ALLHAVEN_FINDINGS.md`.

| ID | Area | Feature | Frontend | Backend/API | Database / integration | Audit status |
|---|---|---|---|---|---|---|
| F-001 | Entry | Root landing and authenticated redirect | `/` | Auth session lookup | Session cookie | PASS |
| F-002 | Auth | Registration and login | `/login` | `/auth/register`, `/auth/login` | `local_users`, profile/workspace provisioning, optional Supabase Auth | PASS on `localhost`; FAIL on the supported-looking `127.0.0.1` alias |
| F-003 | Auth | Session restore and refresh | App shell | `/auth/me`, `/auth/refresh` | `user_sessions` | PASS |
| F-004 | Auth | Logout and profile update | Sidebar/settings | `/auth/logout`, `GET/PATCH /auth/me` | Profiles and session revocation | PASS |
| F-005 | Dashboard | Operational overview and counts | `/dashboard` | Aggregated module reads | Tasks, finance, routines, integrations | PASS for tested data |
| F-006 | Navigation | Sidebar, mobile drawer, modules menu, command palette | Shared app shell | Route navigation | Browser history/session | PASS |
| F-007 | Tasks | Task create/read/update/delete | `/dashboard/tasks` | `/tasks` CRUD | `tasks` | PARTIAL: CRUD works; delete lacks confirmation/undo |
| F-008 | Tasks | Checklist create/update/delete | Task page | `/tasks/{id}/checklist` | `task_checklist_items` | PASS |
| F-009 | Tasks | Complete and reopen state transitions | Task page | `/tasks/{id}/complete`, `/reopen` | Status/completion timestamp | PASS |
| F-010 | Notes | Notes CRUD and tags | `/dashboard/notes` | `/notes` CRUD | `notes` | PASS |
| F-011 | Finance | Finance categories | `/dashboard/finance` | `/finance/categories` | `finance_categories` | PASS by API/source; UI route loads |
| F-012 | Finance | Transaction CRUD, filtering, validation | `/dashboard/finance` | `/finance/transactions` | `transactions` | PASS |
| F-013 | Finance | Summary and report aggregation | Finance dashboard | `/finance/summary`, `/finance/report` | Transaction aggregation | PASS for tested arithmetic |
| F-014 | Routine | Routine/event CRUD | `/dashboard/routines` | `/routines/events` | `calendar_events` | PASS |
| F-015 | Routine | Batch creation, generation, sync status | Routine page | `/routines/events/batch`, `/generate`, `/sync-status` | Google/provider-dependent paths | PARTIAL: local CRUD works; external generation/sync unavailable |
| F-016 | Calendar | Calendar compatibility route | `/dashboard/calendar` redirects to routines | `/calendar/events` | `calendar_events` | PASS; redirect is intentional |
| F-017 | Drive | Drive configuration and listing | `/dashboard/drive` | `/drive/config`, `/drive/files` | Local storage metadata | PASS |
| F-018 | Drive | Upload, safe filename, download, delete | Drive page | `/drive/files`, download/delete | Workspace storage directory | PASS for small files; upload resource cap is unsafe |
| F-019 | AI | Single-provider chat | `/dashboard/ai` | `/ai/chat` | Chat messages/sessions, configured provider | PARTIAL: honest fallback verified; real provider blocked |
| F-020 | AI | Chat groups and sessions | AI page/sidebar | `/ai/groups`, `/ai/sessions` | `chat_groups`, `chat_sessions`, `chat_messages` | PASS for CRUD/ownership paths tested |
| F-021 | AI | Multi-agent chat | AI page | `/ai/chat/multi` | Provider slots and run records | BLOCKED: no external AI providers configured |
| F-022 | AI | Debate mode | AI page | `/ai/chat/debate` | Provider-dependent | BLOCKED |
| F-023 | AI | Reasoning mode | AI page | `/ai/chat/reason` | Provider-dependent | BLOCKED |
| F-024 | AI | Agent run inspection | AI page | `/ai/runs/{id}` | Multi-agent run/response tables | BLOCKED beyond source/test-suite coverage |
| F-025 | AI | Tool proposals and approval/rejection | `/dashboard/approvals` | `/ai/proposals` actions | Tool proposals and audit records | PARTIAL: page/authorization verified; live provider proposal blocked |
| F-026 | AI | Tool registry and enablement | Settings/AI | `/ai/tools`, `/ai/tools/{name}` | Workspace tool policy | PARTIAL: API/source discovered; destructive tools not exercised |
| F-027 | AI | AI policy and chat settings | Settings/AI | `/ai/policy`, `/ai/settings/chat` | Agent/workspace configuration | PASS by test suite/source; route loads |
| F-028 | AI | Provider configuration, slots, enable/test | Settings | `/ai/providers` and slot endpoints | Encrypted provider secrets | PARTIAL: configuration UI exists; live providers blocked |
| F-029 | Knowledge | Knowledge upload/list/read/delete | `/dashboard/ai/knowledge` | `/knowledge/documents` | Documents and chunks | PASS for text document; resource-limit issue remains |
| F-030 | Knowledge | Index, search, and reindex | Knowledge page | `/knowledge/search`, `/reindex` | `ai_knowledge_chunks` | PASS for tested text document |
| F-031 | Memory | Memory CRUD and enable/disable | `/dashboard/ai/memory` | `/memory` CRUD/actions | `ai_memories` | PASS |
| F-032 | Memory | Search, suggestions, settings, clear, Supabase sync | Memory page/settings | `/memory/search`, settings, suggestions, sync | Memory/suggestion tables and Supabase | PARTIAL: local paths pass; remote sync disruption not exercised |
| F-033 | Automation | Automation CRUD and enable state | `/dashboard/automations` | `/automations` | `automations` | PASS |
| F-034 | Automation | n8n workflow list and activation | Automation page | `/n8n/workflows` | n8n | BLOCKED: n8n not configured; UI/API report this honestly |
| F-035 | Approval | Pending action review | `/dashboard/approvals` | AI proposal APIs | `ai_tool_proposals` | PARTIAL: empty state and route pass; live approval workflow blocked |
| F-036 | Settings | Profile, preferences, privacy/safety UI | `/dashboard/settings` | Profile and settings APIs | Profile/preferences | PARTIAL: main settings paths inspected; every preference permutation not exercised |
| F-037 | Settings | Integration list/configure/test/enable/disable/delete | Settings integrations | `/settings/integrations` | `integration_configs` | PARTIAL: status semantics inspected; third-party tests blocked |
| F-038 | Integration | Google OAuth connect/callback/disconnect/scopes | Settings | Google auth/settings endpoints | Google OAuth/Calendar | BLOCKED: credentials and interactive consent unavailable |
| F-039 | Integration | Supabase connection and sync status | Settings | `/settings/supabase/connect`, `/sync/status` | Supabase Auth/REST | PARTIAL: registration mirroring and background sync observed; failure/recovery not stress-tested |
| F-040 | System | Service/agent health dashboard | `/dashboard/settings/system` | `/system/status` | Docker/agent/port probes | FAKE SIGNAL: frontend and database shown stopped while running |
| F-041 | System | Service controls, logs, and port changes | System settings | system action/log/port endpoints | Haven Agent | BLOCKED in production profile because agent is intentionally unavailable |
| F-042 | Utility | Calculator | `/dashboard/calculator` | Client-side | None | PASS route/smoke; exhaustive numeric edge cases not run |
| F-043 | Utility | Clock/timer UI | `/dashboard/clock` | Client-side | Browser timer | PASS route/smoke; long-duration drift not measured |
| F-044 | Notifications | Notification control/panel | Top bar | No independent notification delivery service discovered | UI state only | PARTIAL: control renders; no end-to-end push/delivery channel exists to test |
| F-045 | UI | Responsive app shell | All authenticated pages | N/A | Browser viewport | PASS at 320, 375, 430, 768, 1024, and 1440 px on representative pages |
| F-046 | Security | Cookie auth, CSRF, CORS, workspace isolation | Shared API client | Auth dependencies/middleware | Sessions/workspaces | PARTIAL: CSRF and isolation pass; one local-origin CORS defect |
| F-047 | Data | PostgreSQL schema and Alembic migrations | N/A | SQLAlchemy | PostgreSQL, migration `0020_ai_memory_soft_delete` | PARTIAL: migration current; only one DB foreign key exists |
| F-048 | Data | Local-first Supabase background synchronization | Status/settings | Sync engine | `sync_state`, Supabase | PARTIAL: active sync rows observed; outage/conflict soak test blocked |
| F-049 | Operations | Docker Compose, startup scripts, installer | N/A | Frontend/backend services | Docker/PostgreSQL | PASS for config/build/running stack; blank-host install blocked |
| F-050 | Mobile | Capacitor Android bearer/Supabase data mode | Mobile build code | Bearer auth and REST | Capacitor Preferences/Supabase | SECURITY ISSUE; APK/device runtime blocked |
| F-051 | Operations | Health/version/deployment profile | N/A | `/health` | Backend and primary DB mode | PASS; returned `ok`, version 4.2.0, production/private/local DB |
| F-052 | Security | Production headers and docs exposure | Next.js responses | Middleware/docs routing | CSP/CORS/security headers | PARTIAL: docs disabled and core headers present; CSP permits inline scripts |

## Scope notes

- No hidden weather page is present in the current frontend; weather remains only in residual backend/schema tables and is not counted as a reachable end-user feature.
- No WebSocket or SSE transport was discovered.
- Repository keyword matches for `TODO` were task-status constants, and `PLACEHOLDER` matches were credential-placeholder detection logic; neither was treated as an unfinished feature.
- All external-provider outcomes without credentials or services are marked `BLOCKED` or `PARTIAL`, never `PASS`.
