# Changelog

All notable changes to **AllHaven Command Center** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.
A bigger change means a bigger bump (see [`docs/VERSIONING.md`](docs/VERSIONING.md)).
Full, detailed notes for every release live in [`docs/releases/`](docs/releases/).

## [Unreleased]

- _Nothing yet._

## [4.1.0] - 2026-06-27 — Dashboard chart, Notes edit, and memory correction

Detailed notes: [`docs/v4/RELEASE_NOTES_v4.1.0.md`](docs/v4/RELEASE_NOTES_v4.1.0.md)

- **Finance chart rendering fixed.** Cashflow charts now show visible bars with a stable baseline
  and an honest empty-period state.
- **Notes editing restored.** Existing notes can be opened, edited, saved, pinned, and cleared
  without creating duplicate notes.
- **AI Memory corrected.** Relationship facts such as "pacar saya Kelly" are stored as current
  profile facts; noisy insult-like chat is not auto-learned; context keeps the newest single-value
  profile fact so old contradictions do not confuse the model.
- **Security maintenance.** Next.js upgraded to 15.5.19 and local CORS restricted to trusted
  localhost/LAN/Tailscale/Capacitor origins.

## [4.0.0] - 2026-06-20 — Full Mobile Parity + Tailscale Bridge + Release-Grade Stability

Detailed notes: [`docs/v4/RELEASE_NOTES_v4.0.0.md`](docs/v4/RELEASE_NOTES_v4.0.0.md) · plan: [`docs/v4/`](docs/v4/)

- **Full mobile parity + setup-required states.** Every active desktop module is reachable
  from mobile; backend/bridge-dependent features (Drive, AI Knowledge, integration & AI-provider
  config, n8n) show an actionable `SetupRequiredState` instead of any "use the desktop app" wall.
- **Tailscale Desktop Bridge.** A connection resolver reaches desktop-local **Ollama**/**n8n** by
  mode (local / tailscale-private / serve / funnel; **Funnel off by default**). Status is honest —
  online only if the resolved endpoint responds. Ollama **chat inference** now uses the same
  resolver. API-key AI providers stay **independent of Tailscale**.
- **Deployment profiles** — `private` / `client_portal` / `public_demo` (`DEPLOYMENT_PROFILE`).
- **Version visibility** — `GET /health` returns `app_version` + `deployment_profile`; a single
  version source (VERSION) flows to backend, login, sidebar, and Settings; consistency test.
- **Weather removed** from active scope (dormant tables/migrations kept to avoid destructive change).
- **Carries v3.9 AI fixes** — finance-first deterministic intent routing (money never stored as
  memory), robust Indonesian money parsing, cross-device approvals (two-way sync, no double-exec),
  and the desktop CSS-on-update fix.
- **Quality** — backend 471 tests pass; `tsc` + web + mobile builds clean; secret scan clean.
- ⚠️ **Requires** applying Supabase migrations **0016** (mobile register) + **0017** (cross-device
  proposal/suggestion sync) before relying on those in hosted Supabase — see the migration guide.

## [3.8.0] - 2026-06-19 — Mobile full release, unified accounts, perf & weather removal

Detailed notes: [`docs/releases/v3.8.0.md`](docs/releases/v3.8.0.md)

- **Unified accounts (desktop = mobile).** A successful desktop login now keeps the
  Supabase Auth password in lock-step (background, best-effort) and links the profile,
  so the same email + password works on both platforms — no separate "Connect to
  Supabase" step. New signups are unified from registration.
- **Mobile is a full release.** Every feature (AI Chat, Settings, Drive, AI
  Knowledge/Memory, Approvals) is available on mobile again — nothing is cut.
- **Mobile performance.** REST calls fail fast (20s → 6s) instead of freezing the UI;
  the dashboard renders Supabase data immediately and loads integrations in the
  background; the Topbar stops re-polling an unreachable backend.
- **Robust mobile login + clearer errors.** `loadMe` uses `maybeSingle` with explicit
  "account not linked / no workspace" messages; PostgREST `PGRST116` maps to an
  actionable message; workspace-scoped writes are guarded.
- **Desktop CSS fix.** The mobile export no longer contaminates `next dev`'s build dir
  (a `predev` clean), so pages stop loading unstyled.
- **AI approval safety.** create_transaction proposals normalize empty
  `category_id`/`transaction_date`; the approval card shows readable, editable fields;
  "Connect to Supabase" is idempotent.
- **Migration fix.** Revision `0015` id shortened to fit Alembic's `VARCHAR(32)`, so
  `upgrade head` applies on desktop and Supabase.
- **Removed the Weather feature** entirely (UI, API, AI tool, integration); the dormant
  `weather_locations` table is retained for data safety.
- Dashboard weekly expense buckets parse dates in local time (timezone fix).

## [3.7.0] - 2026-06-19 — AllHaven 3.7 two-way Supabase sync + mobile-on-Supabase

Detailed notes: [`docs/releases/v3.7.0.md`](docs/releases/v3.7.0.md)

AllHaven 3.7 introduces a **two-way incremental sync engine** between local
Postgres and Supabase (Last-Write-Wins by `updated_at`, soft-delete tombstones,
echo-suppression) and a **mobile Supabase data layer** so the Android APK talks
directly to Supabase with no AllHaven backend in the path. Mobile login switches
to Supabase Auth; existing users can link via a new "Connect to Supabase" button
in Settings.

### Added
- **Two-way incremental sync.** Background loop merges local Postgres ↔ Supabase
  by `updated_at` watermark (LWW). Deleted rows travel as soft-delete tombstones
  (`deleted_at`). Sync health visible at `GET /settings/sync/status`. Replaces
  the one-way mirror from 3.4.
- **Mobile Supabase data layer.** New client-side data access objects for Tasks,
  Notes, Finance, Calendar, Routines, Automations, Weather locations, and the
  Dashboard query Supabase PostgREST directly. Selected at build time via
  `NEXT_PUBLIC_DATA_MODE=supabase`.
- **Supabase Auth on mobile.** Mobile login authenticates with Supabase Auth;
  web/desktop keep cookie + bearer. New signups provisioned in Supabase via
  service-role on creation; existing users connect via `POST /settings/supabase/connect`.
- **Database migrations 0010 – 0015.** `deleted_at` soft-delete columns (0010);
  `profiles.supabase_user_id` identity mapping (0011); DB-authoritative
  `updated_at` trigger (0012); Supabase RLS with `app_user_id()` /
  `is_member()` helpers (0013, env-guarded); `workspace_members` RLS hardening
  — SELECT-own-row only, writes restricted to service_role (0014); `sync_state`
  watermark table (0015).

### Fixed
- **Login / dashboard timeout.** Session check and dashboard fetch now time out
  instead of spinning forever when the backend is stalled or unreachable.
- **Checklist item soft-delete.** Deleting a checklist item on desktop writes
  `deleted_at` instead of hard-removing the row, preventing sync resurrection.
- **Checklist item ordering.** Items sorted by `position` on desktop maintain the
  same order after a sync round-trip to mobile.

## [3.6.0] - 2026-06-17 — AllHaven 3.6 privacy cleanup

Detailed notes: [`docs/releases/v3.6.0.md`](docs/releases/v3.6.0.md)

A housekeeping release that removes a personal local-path identifier from the
in-repo development notes so the project ships clean as a personal project. No
application code, API, or behavior changes.

### Changed

- **Privacy cleanup of development docs.** Replaced a hard-coded personal home
  path (`/home/<user>/…`) in `docs/SESSION_MEMORY.md` with a generic
  placeholder (`~/CORE-OS-APPLICATION`). The note's meaning is preserved.

## [3.5.0] - 2026-06-14 — AllHaven 3.5 AI routine generation and atomic save

Detailed notes: [`docs/releases/v3.5.0.md`](docs/releases/v3.5.0.md)

AllHaven 3.5 brings AI assistance to Routine. Describe your day and the
configured AI provider drafts a short, realistic set of routine items for the
chosen time-of-day window; you review and edit each draft, then save them
together. Nothing is generated dishonestly and nothing is saved without your
approval.

### Added
- **AI routine generation.** Routine has a "Generate with AI" flow: a prompt plus a Morning/Afternoon/Evening window produces draft routines via the workspace's configured provider, using your open tasks and same-day routines as optional context. Drafts are generate-only — they are never written to the database.
- **Atomic batch save.** Reviewed drafts are persisted together through a new `POST /routines/events/batch` endpoint. Every item is validated first, so if any one is invalid nothing is saved — no partially-applied batches.
- **Routine sync status card.** The Routine summary now shows whether the workspace Supabase mirror is `active` or running `local_first`, via a new `GET /routines/sync-status` endpoint that degrades gracefully.

### Changed
- **Routine page refactored into components.** The routines dashboard page is split into focused, reusable pieces (DateStrip, PeriodSection, SummaryCards, RoutineToolbar, GenerateModal, RoutineFormModal, and shared helpers) for a lighter, clearer UI.

### Fixed
- **Honest AI provider states.** Generation surfaces a clear `not_configured` state when no provider is set, preserves a configured-but-disabled provider's specific "enable it in Settings" message instead of telling you to configure it again, and reports an honest error on unparseable output rather than a silent empty success.
- **Server-side draft validation.** Drafts are validated and normalized server-side — slot-aware times snapped into the chosen window, capped at 8, with title, length, repeat-rule, and weekday checks — before they reach the review modal.
- **Save controls match what saves.** The review modal disables draft editing while a save is in flight and only enables "Save all (n)" for the count that will actually persist.

## [3.4.0] - 2026-06-13 — AllHaven 3.4 voice, documents, Routine agenda, and local-first sync

Detailed notes: [`docs/releases/v3.4.0.md`](docs/releases/v3.4.0.md)

AllHaven 3.4 focuses on making the workspace feel more natural to use: voice
dictation in chat, PDF/DOC/DOCX knowledge intake, a lighter Routine agenda, and
broader local-first Supabase mirroring for the main app data.

### Added
- **Voice note input.** AI Chat now has a microphone control that uses browser speech recognition to turn voice into a chat prompt when supported.
- **Document attachments from chat.** Chat can upload PDF, DOC, DOCX, text, and code files directly into AI Knowledge before sending a message.
- **PDF/DOC/DOCX knowledge extraction.** AI Knowledge now extracts searchable text from DOCX, simple/standard PDFs, and best-effort legacy DOC files, with honest metadata-only fallback.
- **Workspace-wide Supabase mirror.** Optional Supabase sync now mirrors tasks, checklist items, notes, finance, routines, weather locations, drive metadata, automations, provider/integration config rows, chat, memory, AI Knowledge, proposals, tool logs, and audit rows after local writes.

### Changed
- **Routine agenda redesign.** Routine is now a lighter agenda/timeline instead of large box-heavy cards, with Pagi, Siang, and Malam sections kept clear.
- **Add Routine simplification.** The modal now focuses on name, repeat, days, time, all-day, place, and notes. Icon and color controls are removed from the user flow.
- **AI Routine tools.** Routine tool schemas no longer ask models for icon/color payloads.

### Fixed
- **AI module coverage tests.** Added registry tests that lock in tool access for tasks, routines, finance, notes, files, AI Knowledge, and memory.
- **Supabase sync resilience.** A missing Supabase table no longer stops the rest of the mirror; local data remains the source of truth.

### Security
- **Hardened DOCX parsing.** The new OOXML parser now uses `defusedxml`, so a malicious uploaded DOCX cannot trigger XXE or billion-laughs entity expansion; such files are refused and stored metadata-only.

## [3.3.1] - 2026-06-13 — AllHaven 3.3.1 local Routine UX polish

Detailed notes: [`docs/releases/v3.3.1.md`](docs/releases/v3.3.1.md)

AllHaven 3.3.1 makes Routine more comfortable and clearly local-first: no
Google Calendar requirement, lighter habit-style creation, and better empty
states for planning Pagi, Siang, and Malam.

### Added
- **Routine habit-style builder.** Routine creation now supports icon, color, repeat rule, repeat days, and Pagi/Siang/Malam time slots.
- **Routine local metadata.** Local schedule records now store routine preferences in the database via migration `0009_routine_preferences`.

### Changed
- **Routine board UX.** Pagi, Siang, and Malam lanes stay visible even when empty, giving users direct add targets instead of a blocking empty state.
- **Routine form simplification.** Removed the routine goal field so the create/edit flow focuses on schedule, repeat, visual identity, and notes.

### Fixed
- **Routine loading fallback.** The frontend falls back to the compatible local `/calendar/events` endpoint if `/routines/events` is unavailable after a frontend update but before a backend restart.
- **Local-first copy.** Routine now clearly states that schedules are stored in the AllHaven backend database and do not require Google Calendar.

## [3.3.0] - 2026-06-13 — AllHaven 3.3 Routine planner and sidebar flow

Detailed notes: [`docs/releases/v3.3.0.md`](docs/releases/v3.3.0.md)

AllHaven 3.3 replaces the old Calendar surface with a clearer Routine planner
and reorganizes the main sidebar around the user's daily workflow.

### Added
- **Routine planner.** New `/dashboard/routines` page with a seven-day calendar strip, Today/Upcoming/Selected/All views, routine stats, next-routine summary, jump-to-date control, and a full date/time create/edit modal.
- **Routine API alias.** New `/api/v1/routines/events` endpoints backed by the existing local event storage so old schedule data stays intact.
- **Calendar redirect.** `/dashboard/calendar` now redirects to `/dashboard/routines` for old bookmarks.

### Changed
- **Sidebar order.** Primary navigation now reads: Dashboard, AI Chat, Routine, Task, Finance, Notes, Approval.
- **Dashboard polish.** Routine is now surfaced as a quick action and the dashboard intro copy reflects routines as a first-class workspace area.
- **AI schedule context.** The `routines` section prioritizes schedule/event tools, and user-facing AI tool labels/copy refer to Routine instead of Calendar.

### Compatibility
- Existing `calendar_events` records and `/api/v1/calendar/events` remain available.

## [3.2.0] - 2026-06-13 — AllHaven 3.2 repository hygiene and render skeletons

Detailed notes: [`docs/releases/v3.2.0.md`](docs/releases/v3.2.0.md)

AllHaven 3.2 tightens repository hygiene and adds polished render skeletons so
page transitions no longer fall back to plain empty states while the app loads.

### Added
- **App-wide render skeletons.** Next.js route loading now shows a full application skeleton with sidebar, topbar, header, stat blocks, chart placeholders, and side panels.
- **Dashboard-specific loader.** Dashboard routes get a denser skeleton layout that matches the app shell while pages hydrate or load.

### Changed
- `Skeleton` now accepts standard div attributes for more flexible responsive loader shapes.
- Version metadata is synchronized across `VERSION`, package files, backend metadata, and the in-app `APP_VERSION`.

### Removed
- Local environment files were removed from the working tree while keeping safe templates (`.env.example`, `.env.prod.example`, `frontend/.env.local.example`) for fresh clones.

### Archive
- The `master` archive is clarified so the `0.1` through `1.3` line is treated as **CoreOS**.
- `CoreOS 1.2` maps to semantic `v0.1.0`; `CoreOS 1.3` maps to semantic `v0.2.0`.

## [3.1.0] - 2026-06-13 — AllHaven 3.1 expanded AI agents and settings UX

Detailed notes: [`docs/releases/v3.1.0.md`](docs/releases/v3.1.0.md)

AllHaven 3.1 focuses on the AI control room: more usable model selection,
expanded provider coverage, stronger debate output, and a cleaner Settings layout.

### Added
- **10-agent multi-agent cap.** Parallel, Debate, and Reasoning now accept up to 10 selected agents per run, with new default roles for Data/Numbers, Scheduler, Creative/Tone, and Synthesizer coverage.
- **Cursor AI provider.** Adds a Cursor-compatible coding provider with `Cursor 1` and `Cursor 2` model slots. It requires an explicit Cursor/OpenAI-compatible base URL so AllHaven never pretends a non-chat Cursor endpoint is online.
- **DeepSeek and Qwen providers.** Adds first-class DeepSeek and Alibaba Qwen/DashScope providers through OpenAI-compatible chat adapters, with `.env` mirror keys for local persistence.
- **Searchable model picker.** AI Chat's Add Agent menu now supports search, groups direct providers separately from OpenRouter, and labels slots as GPT 1/2, Gemini 1/2, Cursor 1/2, DeepSeek, Qwen, and so on.

### Changed
- **Debate output polish.** Debate prompts now keep each agent direct, concrete, and honest, carry memory/context into rebuttal rounds, and ask the synthesizer for a cleaner final answer with less repetition.
- **Settings → AI Providers layout.** Provider setup now starts with compact health stats, then separates Direct model agents from OpenRouter agents for easier scanning.
- **Provider cards and slot editor.** Cards preview available slots, and the configure modal has a wider, clearer two-column layout.
- **AI Chat Behavior cap.** The workspace `max_active_agents` setting now allows 1-10 instead of 1-7.

### Fixed
- Provider tests and env-sync allowlists now cover Cursor, DeepSeek, and Qwen.
- Version metadata is synchronized across `VERSION`, package files, backend metadata, and the in-app `APP_VERSION`.

## [3.0.0] - 2026-06-13 — AllHaven 3.0 launch-ready AI workspace

Detailed notes: [`docs/releases/v3.0.0.md`](docs/releases/v3.0.0.md)

A launch-focused AllHaven 3.0 release: app-wide layout refinement, stronger AI
Knowledge access, user preferences, and in-app decision popups.

### Changed
- **Sidebar polish.** Clear Workspace/Modules hierarchy, stronger active states, icon wells, refined badges, a premium New Command button, and a cleaner profile/footer area.
- **Top navigation polish.** Search, local AI status, settings, avatar, and approval notifications now share the same compact visual language.
- **Command palette polish.** The search overlay now matches the topbar/sidebar style, with clearer active rows and icon treatment.
- **Shared UI polish.** Cards, buttons, icon buttons, inputs, panel shadows, hover states, and page headers now have more consistent spacing, radius, borders, and focus behavior.
- **Dashboard polish.** The dashboard now opens with a tighter workspace summary, quick links to Approvals and AI Chat, cleaner stat tiles, and better responsive grid behavior.
- **AI Knowledge availability.** Every chat mode/model now receives a light AI Knowledge inventory and can retrieve relevant indexed chunks, including Fast mode.
- **User preferences.** Settings now exposes language, dark/light theme, and accent color controls that apply across the app shell and AI response instructions.
- **In-app decision popups.** Browser `alert`/`confirm`/`prompt` calls for chat, memory, knowledge, and alarms are replaced with AllHaven modals/toasts.

### Fixed
- Synchronized version metadata across `VERSION`, root package, frontend package/lockfile, backend package metadata, and the in-app `APP_VERSION`.
- Local date/time answers now respect the selected language when they bypass an AI provider.

## [0.17.0] - 2026-06-13 — AI Workspace, Knowledge, finance reports & direct memory

Detailed notes: [`docs/releases/v0.17.0.md`](docs/releases/v0.17.0.md)

A full-stack workspace release: AI context becomes section-aware, AI Knowledge is now a
first-class module, finance gets weekly/monthly reports, and the assistant becomes more
direct, conversational, and useful for coding plus schedule management.

### Added
- **AI Knowledge module.** Upload/index/search/retrieve workspace documents from the dashboard and from the AI Tool Registry. Current text extraction supports `.txt`, `.md`, and `.csv`; other file types are stored with honest indexing status until parsers are added.
- **Section-aware AI context packets.** Single chat, one-agent Parallel, Debate, and Reasoning now receive active section, thinking mode, tool priority, relevant memory, conversation summaries/snippets, and AI Knowledge context when useful.
- **Dedicated AI tool-call logging.** Tool calls are persisted in `ai_tool_calls` with redacted arguments/results for auditing and debugging.
- **Expanded Tool Registry.** The registry now exposes 72 allowlisted tools, including conversation search, task/note draft aliases, finance summaries, file metadata, AI Knowledge retrieval, and local date/time tools.
- **Finance reports.** Finance now supports custom report ranges with weekly and monthly views, trend bars, and report-scoped totals.
- **Archived/out-of-period finance handling.** Old records such as 2023 transactions are shown as outside the selected 2026 report and can be moved into the active week/month from the UI.
- **Local date/time answers.** The AI can answer "jam berapa" / current date questions instantly from the app timezone, even without a configured AI provider.
- **Configurable Drive upload limit.** `DRIVE_MAX_UPLOAD_MB` controls backend and frontend upload limits, defaulting to 250 MB.

### Changed
- **Memory can be faster.** Low-risk memory create/update/disable actions now save directly; destructive or higher-risk memory actions still require approval.
- **AI tone and behavior.** Prompts now keep routine replies direct/no basa-basi while still allowing casual chat, jokes when invited, serious work mode, senior coding help, and schedule/task/calendar assistance.
- **Pending action UI.** Approval/rejection feedback is now a short toast-style notification; the pending panel stays focused on actions that still need a decision.
- **Memory ranking and UI.** The memory context builder prioritizes profile, preferences, writing style, work context, and relevant recent memories; the memory page exposes richer metadata and easier editing.

### Fixed
- **Finance no longer looks "empty" without context.** When the active report is empty but older records exist, the UI explains why those transactions are not counted and offers a move action.
- **AI-created finance transactions default to today.** If the user does not specify a transaction date, finance tools now use the app's current date instead of forcing the model to invent one.

### Database
- **Migration `0008_ai_workspace_tools_and_knowledge`.** Adds `chat_sessions.section_key`, `chat_messages.section_key`, `ai_tool_calls`, `ai_knowledge_documents`, and `ai_knowledge_chunks`. **Run `python -m alembic upgrade head` after pulling.**

## [0.16.0] - 2026-06-12 — Persistent AI memory system

Detailed notes: [`docs/releases/v0.16.0.md`](docs/releases/v0.16.0.md)

A full-stack feature release — new backend services, REST API, DB migration, and frontend pages.

### Added
- **Persistent AI memory.** A workspace-scoped memory store that survives restarts. Memories are created automatically as you chat (hybrid: rule-based fast-path + async LLM background extraction) and can be managed manually. **Secret detection** runs on every candidate before it is saved, and any memory flagged as sensitive enters an **approval queue** rather than landing directly in the store.
- **Memory context injection.** All four chat modes — single-agent, multi-agent parallel, debate, and reasoning — receive the workspace memory as a system-level prefix. Each injection is keyed by `section_key` so memories stay section-scoped and can be injected selectively.
- **Memory tools (Tool Registry).** Five new tools (`memory_list`, `memory_search`, `memory_create`, `memory_update`, `memory_delete`) are registered in the Tool Registry. Write operations (`create`, `update`, `delete`) follow the existing human-approval pattern — the AI proposes, you approve.
- **REST API `/ai/memory/*`.** Full CRUD and search endpoints: `GET /ai/memory/`, `POST /ai/memory/`, `GET /ai/memory/{id}`, `PATCH /ai/memory/{id}`, `DELETE /ai/memory/{id}`, `POST /ai/memory/search`, plus a `GET /ai/memory/pending` queue for approval suggestions.
- **Memory management page** (`/dashboard/ai/memory`). Browse, search, approve, edit, and delete memories from the dashboard. Approval-pending items are surfaced prominently.
- **In-chat MemoryIndicator.** A subtle indicator in every chat mode shows when memory context is active and lets you navigate to the memory page.
- **AI Memory nav link.** A top-level navigation entry under AI links to the new management page.
- **Supabase background sync (opt-in).** An optional one-way sync pushes memories to a Supabase table for cross-device access. Disabled by default; enable via `SUPABASE_URL` + `SUPABASE_ANON_KEY` in `.env`.
- **Migration `0007_ai_memories`.** Three new DB tables: `ai_memories`, `ai_memory_tags`, `ai_memory_sync_log`. **Run `python -m alembic upgrade head` after pulling.**

## [0.15.0] - 2026-06-12 — Premium UI polish, persistent model selection & per-section chat memory

Detailed notes: [`docs/releases/v0.15.0.md`](docs/releases/v0.15.0.md)

A frontend/UX release — no backend or API changes.

### Added
- **Persistent model selection.** AI Chat now remembers your selected **agents/model**, **chat mode** (Parallel/Debate/Reasoning), **Thinking depth**, and debate rounds across page navigation and browser refresh. On load the saved selection is **reconciled against available providers** — unavailable models are dropped with a clear notice and a sensible fallback (or "Configure an AI provider first"). The workspace default only applies on a fresh device.
- **Per-section chat memory.** Each module section (General, Tasks, Notes, Finance, Calendar, Files, Automations, Weather, Settings, System Control) **and each chat project/group** keeps its own **local, editable memory** (`title` / `summary` / important-context bullets). Pick the section from the chat header, view/edit/clear it, and the AI uses it to give more relevant answers (injected once per thread). **Secrets are auto-redacted** before saving; clear per-section or all.
- **Local storage abstraction** (`lib/storage.ts`) — namespaced, versioned, SSR-safe, IndexedDB-ready — backing both features.
- **Smooth micro-animations** — route/page transitions, dropdown/popover entrances, chat message-in, and the pending-actions panel — all 120–250ms with soft easing and a global **`prefers-reduced-motion`** guard.

### Changed
- **Polished Finance & Settings.** Finance KPI cards gain clearer hierarchy (icon chips, tabular figures, hero balance with negative-aware color); Settings tab switches now fade in.
- Chat header reorganized to surface the active **Section / Memory** controls without crowding.

### Fixed
- **No more session-check flash on every navigation** — the session is confirmed once per page-load, so moving between dashboard pages no longer flashes the "Checking your session…" loader.

## [0.14.0] - 2026-06-11 — Terminal-only install (browser wizard now opt-in) + faster Docker check

Detailed notes: [`docs/releases/v0.14.0.md`](docs/releases/v0.14.0.md)

### Changed
- **Install is terminal-only again.** `START_HAVEN_*`, `./install.sh`, and `npm run setup` now install & start Haven **entirely in the terminal** (the proven `haven_cli.py` flow, with live Docker/`pip`/`npm` progress). The browser Setup Wizard had recurring issues (the local setup server erroring on stop, and a slow Docker-detection step), so it is **no longer the default** — it remains available **opt-in** via `HAVEN_SETUP_WEB=1`.
- **Launchers branch on setup state:** first run → terminal installer; already configured → start services + open the app (what the desktop shortcut uses). `HAVEN_FORCE_SETUP=1` re-runs the installer.
- **Faster Docker check:** the daemon probe timeout dropped from 8s to **4s**, and the terminal path checks the daemon once (the web wizard's repeated multi-probe detection — the slow part — is no longer in the default flow).

## [0.13.0] - 2026-06-11 — GUI-first install: terminal bootstraps the Setup Wizard

Detailed notes: [`docs/releases/v0.13.0.md`](docs/releases/v0.13.0.md)

### Changed
- **Install is now GUI-first.** The terminal command is only a **bootstrapper**: it checks for Python, starts the local setup server, and **opens the browser Setup Wizard**, where ALL configuration happens (OS/Docker checks, Docker install guide, ports, `.env` setup/update with backup, start services, health check, desktop shortcut, open app). New entry points `./install.sh` and `npm run setup` join `START_HAVEN_*`.
- **Launchers branch on setup state:** first run (no `.env`) → the **Setup Wizard**; already set up → the launcher that ensures services are running and opens the app. The **desktop shortcut** uses that same launcher, so clicking it post-install starts services safely and opens Haven — never the wizard. `HAVEN_FORCE_WIZARD=1` re-opens the wizard; `HAVEN_SETUP_CLI=1` keeps the terminal-only installer.

### Added
- **Live install progress in the wizard.** The Start step tails the install log (Docker image pull, `pip install`, `npm install`) + the backend log via a new masked `/api/setup/log` endpoint, so the first run shows real progress instead of appearing to hang — and auto-advances when the backend & frontend are healthy.

## [0.12.0] - 2026-06-11 — App-wide AI tools with human approval, 6 OpenRouter slots, 7-agent roles

Detailed report: [`docs/releases/v0.12.0.md`](docs/releases/v0.12.0.md)

### Added
- **AI Tool Registry** — 35 allowlisted, schema-typed tools connect AI Chat to every module (time, tasks, calendar, notes, finance, files, weather, automations, system control). **Read** tools execute instantly; **write** tools always create a **pending approval** — the AI can never change data silently. Every call is audited.
- **Human approval execution** — Approve (executes via the registry), **Edit payload**, or Reject each pending action from the new in-chat **Pending actions** panel. HIGH-risk tools (file delete, enabling workflows, service control) require approval even when a workspace relaxes approvals.
- **Native tool calling** on the OpenAI-compatible provider family (OpenAI, Grok, all OpenRouter agents); single-agent chat is now conversation-history-aware. Other providers chat honestly without tools (no fake claims).
- **Six OpenRouter agents** (`openrouter_1..6`, each with its own key/model/suggested role) — 12 providers total.
- **Model slots** — every other provider gets 2 slots (a secondary model selectable as "Provider · Slot 2"), with editable roles.
- **Up to 7 agents per run** (was 3), each with a distinct role (Main, Planner, Research, Coder, Critic/Risk, Product/UX, Synthesizer) — slot roles override defaults.
- **Debate-flow visibility toggle** — hide the transcript and show only the polished final answer ("N agents collaborated"), persisted per workspace.
- **Settings → AI Tools** (enable/disable per tool, risk + approval badges) and **Settings → AI Chat** (default mode, approval requirement, tool activity, polish level, max agents).

### Changed
- Debate/Reasoning **synthesizer prompts** upgraded: direct answer first, concrete and specific, no generic filler, contradictions resolved, warnings preserved, honest uncertainty, replies in the user's language.

## [0.11.0] - 2026-06-10 — Terminal installer + backend/.env sync + faster Docker check

Detailed notes: [`docs/releases/v0.11.0.md`](docs/releases/v0.11.0.md)

### Added
- **Terminal installer** (`installer/haven_cli.py`). The `START_HAVEN_*` launchers now run a terminal-first setup **by default** that shows **live progress** for the slow steps (Docker image pull, `pip install`, `npm install`), then starts the app and opens the browser. Idempotent — first run installs everything, later runs just start. The browser wizard is still available via `HAVEN_SETUP_WEB=1`.

### Fixed
- **`backend/.env` now follows the repo-root `.env`.** Generating or updating `.env` (terminal installer, web wizard, or any service start) mirrors it to `backend/.env` and re-syncs whenever it changes — so the backend always sees the same configuration you just set.
- **Docker check no longer appears to hang.** The daemon probe uses a lighter `docker version` query with a shorter (8s) timeout, and the terminal installer **streams `docker compose` output**, so a first-run image pull shows real progress instead of a frozen spinner.

## [0.10.0] - 2026-06-10 — Reliable one-click startup + responsive menu

Detailed notes: [`docs/releases/v0.10.0.md`](docs/releases/v0.10.0.md)

### Fixed
- **Services now start reliably from the launcher/wizard.** Previously the backend could be unreachable when started via the app even though manual runs worked. The launch path is now faithful to `allhaven.sh`: it binds services to `0.0.0.0` (not `127.0.0.1`, which a `localhost`→IPv6 lookup can miss), creates `frontend/.env.local`, **waits for PostgreSQL**, runs `alembic upgrade head`, **health-gates** the backend, enriches `PATH` for GUI launches, and **installs missing dependencies on first run** (venv + pip, `npm install`). Failures now surface a masked log tail instead of failing silently.
- The setup wizard's "Start" step and the desktop shortcut both drive the one proven launcher path (`installer/haven_launch.py`).

### Changed
- **Responsive, polished navigation menu:** a collapsible desktop rail (persisted, with tooltips), a persistent icon rail on tablets (`md`+) with the full sidebar at `xl`, a signed-in user chip, refined active/hover states, and accessibility (`aria-current`, focus rings). The mobile drawer is retained for small screens.

### Security
- The control agent still binds **127.0.0.1 only**; only the managed app services bind `0.0.0.0` (LAN-reachable, matching the project's default `allhaven.sh` behavior). Logs remain masked.

## [0.9.0] - 2026-06-10 — One-click desktop installer, setup wizard & System Control

Detailed notes: [`docs/releases/v0.9.0.md`](docs/releases/v0.9.0.md)

### Added
- **One-click launchers** at the repo root — `START_HAVEN_WINDOWS.bat`, `START_HAVEN_MAC.command`, `START_HAVEN_LINUX.sh` — that run a **browser-based setup wizard** (`installer/haven_setup.py`, Python stdlib only): OS detect, Docker/ports/`.env` system check, Docker install guidance, port configuration (validation + free-port suggestions), safe `.env` write (backup + preserved secrets), service start, health check, and per-OS **desktop shortcut** creation.
- **Haven Agent** (`installer/haven_agent.py`) — a localhost-only, token-gated process supervisor that safely starts/stops/restarts the backend & frontend (host processes) and Postgres/optional services (Docker Compose, non-destructive), with masked logs. No shell; fixed argv; service + action allowlists.
- **Settings → System Control** (in-app): live service cards (status / port / last-checked), Start / Stop / Restart, a masked **Logs** viewer, and a **Ports editor** ("Save & Restart"). Backed by a new authenticated, allowlisted `/api/v1/system/*` API that forwards to the agent and falls back to read-only status when the agent is offline. Disabled outside local mode.

### Security
- Privileged actions live only in the localhost + token agent; the browser never touches Docker or a shell. Service/action **allowlists** are enforced in both the agent and the backend; secrets are **masked** in all logs/responses; `.env` writes are atomic with timestamped backups; Docker control **cannot express** destructive (`down` / volume) commands; the control surface requires auth and is off outside local mode.

## [0.8.0] - 2026-06-10 — Live n8n workflows in Automations

Detailed notes: [`docs/releases/v0.8.0.md`](docs/releases/v0.8.0.md)

### Added
- **Live n8n integration** on the Automations page: lists your real workflows from the connected n8n (`GET /n8n/workflows`), with **activate/deactivate** toggles (`POST /n8n/workflows/{id}/active`) and an **Open in n8n** link. Backed by the workspace's n8n Base URL + API key (server-side only — the key is never returned to the browser).
- Honest states when n8n isn't ready: `not_configured` / `no_api_key` / `unauthorized` / `unavailable` / `error`, each with guidance to Settings → Connected Tools. No fake "run".
- Local draft definitions are kept and clearly relabeled as **not executed** (the real, runnable automations are the n8n ones).

## [0.7.0] - 2026-06-10 — Public-launch auth: cookie sessions, CSRF, rate limiting

Detailed notes: [`docs/releases/v0.7.0.md`](docs/releases/v0.7.0.md) · Audit: [`LAUNCH_SECURITY_REPORT.md`](LAUNCH_SECURITY_REPORT.md)

### Security
- **HttpOnly cookie sessions replace localStorage tokens** (browser): hashed (SHA-256) server-side session records, `SameSite=Lax`, `Secure` outside local dev; **rotation** via `POST /auth/refresh`; **server-side revocation** via `POST /auth/logout`. Bearer JWT stays available for API clients/tools. A legacy-key scrub removes previously stored tokens from upgraders' browsers.
- **CSRF protection** (double-submit): per-session token in a readable cookie must be echoed in `X-CSRF-Token` on every state-changing cookie-authenticated request (enforced centrally; 403 `CSRF_FAILED`).
- **Auth rate limiting**: per-IP sliding-window cap on `/auth/*` POSTs (`AUTH_RATE_LIMIT_PER_MINUTE`; prod example 10) + gateway guidance for multi-replica.
- **SECRET_KEY production guard**: startup fails in production/staging with the dev default or a key shorter than 32 chars.
- Private routes verify auth via `GET /auth/me` (cookie) — survives refresh without exposing any token to JavaScript.

### Changed
- New table `user_sessions` (migration `0006`). Frontend API client sends `credentials: "include"` + CSRF header; Drive upload/download use cookies.

## [0.6.0] - 2026-06-10 — Launch hardening: security headers, safe downloads & dep patches

Detailed notes: [`docs/releases/v0.6.0.md`](docs/releases/v0.6.0.md) · Audit: [`LAUNCH_SECURITY_REPORT.md`](LAUNCH_SECURITY_REPORT.md)

### Security
- **Security headers** on every backend response (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`) and on the frontend via `next.config.js`, including a production **Content-Security-Policy** (`frame-ancestors 'none'`, `object-src 'none'`, no `unsafe-eval`).
- **Drive downloads** force `Content-Disposition: attachment` and serve active types (HTML/SVG/JS/XML) as `application/octet-stream` — uploaded files can't render inline (XSS).
- **Dependencies**: Next `14.2.18 → 14.2.35` (fixes the critical middleware-authorization-bypass) and `postcss → 8.5.15` tree-wide (fixes moderate stringify-XSS). One residual Next "high" (DoS/cache — features we don't use) documented in the security report.
- Backend reports its real version from `VERSION` (was hardcoded).

### Added
- `LAUNCH_SECURITY_REPORT.md` — full audit (secrets, auth, API, DB, uploads, AI safety, integrations, deps, headers) with verdict + residual risks.


## [0.5.1] - 2026-06-10 — Honest "model can't read images" status

Detailed notes: [`docs/releases/v0.5.1.md`](docs/releases/v0.5.1.md)

### Fixed
- When a vision-capable **provider** (Ollama, OpenRouter, …) is given an image but the selected **model** is text-only, the provider's raw API error (`HTTP 400 multimodal`, `HTTP 404 no endpoints found that support image input`) is now translated into a clear **`unsupported`** status with guidance to pick a vision model — instead of leaking the raw error JSON. Applies to Parallel, Debate, and Reasoning.

## [0.5.0] - 2026-06-09 — Calculator, Clock, Thinking Mode & vision routing

Detailed notes: [`docs/releases/v0.5.0.md`](docs/releases/v0.5.0.md)

### Added
- **Calculator** module (`/dashboard/calculator`): +, −, ×, ÷, %, ±, decimal, clear, backspace, full keyboard support, responsive dark UI.
- **Clock** module (`/dashboard/clock`): live local time/date/timezone, stopwatch with laps, countdown timer with alert, and an alarm foundation (saved locally, rings while open).
- **Thinking Mode** (Fast / Balance / Thinking / Deep) near the chat input — controls reasoning depth + sampling (temperature/top_p), separate from Chat Mode. Default Balance.
- **Provider capability metadata** (`supports_text` / `supports_image` / `supports_tools`) exposed in `GET /ai/providers`; vision-capable models show an eye icon in the agent picker.
- **Vision routing**: images are sent only to vision-capable providers; non-vision providers return an honest `unsupported` status. The composer warns when an attached image won't reach a selected model, and confirms when it's vision-ready. Drag-and-drop image upload added.
- Safe backend arithmetic evaluator (`calc_service`, no `eval`).

### Changed
- Chat modes simplified to exactly **Parallel · Debate · Reasoning**. The reasoning depth/summary controls moved into the bottom Thinking Mode selector. Reasoning depth now derives from Thinking Mode (fast→fast, balance→balanced, thinking/deep→deep).

## [0.4.0] - 2026-06-09 — Image input (vision) & polished chat output

Detailed notes: [`docs/releases/v0.4.0.md`](docs/releases/v0.4.0.md)

### Added
- **Image upload + vision**: attach up to 4 images to a chat turn; vision-capable models receive and respond to them. Images are downscaled client-side, formatted per provider (OpenAI/OpenRouter/Grok/Blackbox, Anthropic, Gemini, Ollama), shown in the thread, and persisted so they survive a reload.
- **Markdown rendering** for AI output — headings, lists, code blocks, bold/italic, blockquotes, and links — so responses read cleanly instead of as one raw blob. Dependency-free renderer (no HTML-injection risk).

### Fixed
- Missing `network_error_message` import in the Ollama, Anthropic, and Gemini adapters (would raise `NameError` on a network failure during chat).

## [0.3.0] - 2026-06-09 — Reasoning Quality Layer

Detailed notes: [`docs/releases/v0.3.0.md`](docs/releases/v0.3.0.md)

### Added
- **Reasoning Quality Layer** (`backend/app/services/reasoning/`): deterministic, model-independent grounding, numeric verification (year-by-year growth, `EBITDA = revenue × margin`, `X% of Y` checks), Porter Five Forces validation, acquisition-direction check, and relevance/grounding/calculation/hallucination scoring with an honest confidence.
- **Reasoning council** (`POST /ai/chat/reason`): Analyst → Critic → Synthesizer roles; the Synthesizer rejects irrelevant/invented critique; the final answer is verified and retried once with stricter grounding when it scores low.
- **Reasoning modes** Fast / Balanced / Deep controlling pipeline depth and sampling temperature.
- Generation parameters (`temperature`, `top_p`, penalties) threaded through every provider adapter.
- Frontend **Reason** mode: Fast/Balanced/Deep selector, reasoning-summary toggle, debug toggle, and a low-confidence/assumptions warning.

### Fixed
- Ollama adapter: missing `network_error_message` import (raised `NameError` on a network failure).

## [0.2.0] - 2026-06-09 — Multi-agent Debate

Detailed notes: [`docs/releases/v0.2.0.md`](docs/releases/v0.2.0.md)

### Added
- **Debate mode** (`POST /ai/chat/debate`): a **Parallel ⇄ Debate** toggle; with 2–3 agents they answer, then critique and refine across rounds, and one agent synthesizes a single best final answer.
- Rounds selector (2–4) and a responsive debate transcript UI (per-round agent cards + highlighted final answer).

## [0.1.0] - 2026-06-09 — Initial AllHaven Command Center

Detailed notes: [`docs/releases/v0.1.0.md`](docs/releases/v0.1.0.md)

### Added
- **Backend**: FastAPI + PostgreSQL, Alembic migrations, JWT auth + workspaces, audit log.
- **Frontend**: Next.js + TypeScript + Tailwind, responsive app shell (mobile drawer), command palette.
- **Modules**: Tasks, Notes, Finance, Drive, Calendar, Weather, Automations.
- **AI**: 9 providers (Ollama, OpenAI, Anthropic, Gemini, Grok, Blackbox, OpenRouter ×3), parallel multi-agent chat, honest provider verification (no fake "online"), Settings with secure `.env` sync.
- **Deploy**: Docker / docker-compose (dev + prod with Caddy HTTPS), `allhaven.sh` helper.

[Unreleased]: https://github.com/joshuasetiawann/AllHaven-Application/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/joshuasetiawann/AllHaven-Application/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/joshuasetiawann/AllHaven-Application/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/joshuasetiawann/AllHaven-Application/releases/tag/v0.1.0
