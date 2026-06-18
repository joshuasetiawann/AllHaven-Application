<div align="center">

![AllHaven Command Center](docs/assets/banner.svg)

# 🛡️ AllHaven — Version Archive

**The complete release history of [AllHaven Command Center](../../tree/main).**

Every version is frozen in its own self-contained archive folder
(`CoreOS 0.1` through `AllHaven 4.2`) — a full, runnable snapshot.
The latest version also lives on the
[`main`](../../tree/main) branch.

![Latest](https://img.shields.io/badge/latest-AllHaven%204.2%20-%20v4.2.0-18E0D6?style=flat-square)
&nbsp;![Releases](https://img.shields.io/badge/releases-44-2563EB?style=flat-square)
&nbsp;![© 2026 Joshua Setiawan](https://img.shields.io/badge/©%202026-Joshua%20Setiawan-555?style=flat-square)

</div>

---

## 📦 About this branch

- **`master`** (this branch) — the **full archive**: every release frozen in its
  own `CoreOS X.Y` or `AllHaven X.Y` folder, a complete snapshot you can open and
  run on its own. The release-history table below lists them in chronological
  order (CoreOS first, then AllHaven).
- **[`main`](../../tree/main)** — only the **latest** version, flat at the repo root,
  ready to run or deploy.

> **Version numbering** runs `0.1 → 0.9`, `1.0 → 1.9`,
> then `2.0` onward. **Era** marks the early **CoreOS** prototype vs. the **AllHaven** product
> (rebranded at 1.4). **Semantic** is the internal `vX.Y.Z`; CoreOS 1.2 maps to
> `v0.1.0`, CoreOS 1.3 maps to `v0.2.0`, and AllHaven 1.4 starts at `v0.3.0`.

## Latest maintenance recap

| Date | Branch | Commit | Summary |
|:--|:--|:--|:--|
| 2026-07-07 | `mobile` | `d536a66` | Rebuilt the standalone Flutter web assets and APK bundle at version `4.2.0+44` after the front-door, bridge, CSP, and Preferences fixes. |
| 2026-07-07 | `mobile` | `d31a813` | Refreshed the mobile source entry flow, AI Backend Bridge setup handling, CSP font origins, and Capacitor Preferences wrapper. |
| 2026-07-07 | `main` | `4250ea6` | Wrapped the Capacitor Preferences API so web/Capacitor runtimes no longer throw `Preferences.then()` during mobile auth hydration. |
| 2026-07-07 | `main` | `3c07db9` | Allowed the app's Google font origins in production CSP so desktop pages no longer log blocked stylesheet/font errors. |
| 2026-07-07 | `main` | `d17bf0c` | AI Chat now shows a clear Backend Bridge setup state when REST-only desktop features are unreachable from mobile/Tailscale. |
| 2026-07-07 | `main` | `acecaa8` | Replaced the old root landing screen with a direct Command Center routing screen for desktop and mobile. |
| 2026-07-07 | `main` | `75cc121` | Mobile builds now require an explicit Backend Bridge URL for REST-only features instead of falling back to localhost. |
| 2026-07-07 | `mobile` | `c266f81` | Rebuilt the standalone APK with Supabase configuration, direct `/login/` startup, Backend Bridge not-configured state, and APK version `4.2.0+43`. |
| 2026-07-07 | `main` | `c6d796c` | Stabilized the mobile static export build id so desktop/latest source no longer emits random APK manifest folders. |
| 2026-07-07 | `mobile` | `bdfa7ad` | Refreshed the standalone Flutter APK bundle to AllHaven 4.2, bumped APK version to `4.2.0+42`, and verified the Android debug build. |

## 🗓️ Release history

| Version | Released | Era | Semantic | What this update introduced |
|:--|:--|:--|:--|:--|
| **CoreOS 0.1** | 2026-06-08 | CoreOS | — | Initial base — FastAPI + PostgreSQL backend, Next.js + TS + Tailwind frontend, auth, and the first modules (Tasks, Notes, Finance). |
| **CoreOS 0.2** | 2026-06-08 | CoreOS | — | UI layer — app layout (PageHeader, nav) and a reusable UI kit (Avatar, BarChart, IconButton, Select, Tabs, Toggle) + user preferences. |
| **CoreOS 0.3** | 2026-06-08 | CoreOS | — | AI provider system — provider router, provider registry, encrypted secrets, integration config service + schemas (migration `0002`). |
| **CoreOS 0.4** | 2026-06-08 | CoreOS | — | New module pages (Drive, Calendar, Weather, Automations) + task checklists (migration `0003`) + the Blackbox provider. |
| **CoreOS 0.5** | 2026-06-08 | CoreOS | — | Google OAuth foundation (router + service + card) and Ollama provider tests. |
| **CoreOS 0.6** | 2026-06-08 | CoreOS | — | Per-workspace **AI policy** — allow/deny external AI providers. |
| **CoreOS 0.7** | 2026-06-08 | CoreOS | — | Command palette (⌘K) for fast navigation/search. |
| **CoreOS 0.8** | 2026-06-08 | CoreOS | — | One-command setup/run helper script. |
| **CoreOS 0.9** | 2026-06-08 | CoreOS | — | Stability fixes and refinements (no new surface). |
| **CoreOS 1.0** | 2026-06-09 | CoreOS | — | **Multi-agent chat + module backends** — concurrent agents and Drive/Calendar/Weather/Automations APIs (migration `0004`). |
| **CoreOS 1.1** | 2026-06-09 | CoreOS | — | Session memory / project documentation. |
| **CoreOS 1.2** | 2026-06-09 | CoreOS | `v0.1.0` | **Production deployment** — Dockerfiles, prod compose with Caddy HTTPS, deploy guide. |
| **CoreOS 1.3** | 2026-06-09 | CoreOS | `v0.2.0` | Cross-OS run scripts + local-setup and release docs. |
| **AllHaven 1.4** | 2026-06-09 | **AllHaven** | `v0.3.0` | Rebrand to AllHaven + responsive UI, **multi-agent Debate** mode, and the **Reasoning Quality Layer** (Analyst → Critic → Synthesizer with grounded, verified reasoning). |
| **AllHaven 1.5** | 2026-06-09 | **AllHaven** | `v0.4.0` | **Image input (vision)** — attach images and have agents respond to them — plus **Markdown-rendered chat output**. |
| **AllHaven 1.6** | 2026-06-09 | **AllHaven** | `v0.5.0` | **Calculator** & **Clock** modules, **Thinking Mode** (Fast/Balance/Thinking/Deep), chat modes simplified to Parallel/Debate/Reasoning, and **vision routing** (images go only to vision-capable models). |
| **AllHaven 1.7** | 2026-06-10 | **AllHaven** | `v0.5.1` | Honest **"this model can't read images — pick a vision model"** status when a vision provider gets an image but the chosen model is text-only. |
| **AllHaven 1.8** | 2026-06-10 | **AllHaven** | `v0.6.0` | **Launch hardening** — HTTP security headers (backend + frontend CSP), safe Drive downloads, and dependency patches. Full audit in `LAUNCH_SECURITY_REPORT.md`. |
| **AllHaven 1.9** | 2026-06-10 | **AllHaven** | `v0.7.0` | **Public-launch auth** — HttpOnly **cookie sessions** (server-side, rotation + revocation), **CSRF** double-submit, `/auth/*` **rate limiting**, and a production **SECRET_KEY guard**. |
| **AllHaven 2.0** | 2026-06-10 | **AllHaven** | `v0.8.0` | **Live n8n workflows** in Automations — list real workflows from the connected n8n, **activate/deactivate**, and **open in n8n** (API key stays server-side). |
| **AllHaven 2.1** | 2026-06-10 | **AllHaven** | `v0.9.0` | **One-click desktop installer** — OS launchers + a browser **setup wizard** (Docker / ports / `.env` checks), a localhost-only **token-gated control agent**, and in-app **Settings → System Control**. |
| **AllHaven 2.2** | 2026-06-10 | **AllHaven** | `v0.10.0` | **Reliable one-click startup + responsive menu** — launch faithful to `allhaven.sh` (bind `0.0.0.0`, wait for PostgreSQL, run migrations, health-gate, install deps, surface logs), fixing *"works manually but not from the app"*. Plus a collapsible, responsive nav menu. |
| **AllHaven 2.3** | 2026-06-10 | **AllHaven** | `v0.11.0` | **Terminal installer + config sync** — install & start from the **terminal by default** with live progress (Docker pull, `pip`, `npm`); `backend/.env` mirrors the root `.env`; faster Docker check. Browser wizard via `HAVEN_SETUP_WEB=1`. |
| **AllHaven 2.4** | 2026-06-11 | **AllHaven** | `v0.12.0` | **App-wide AI tools with human approval** — a safe, allowlisted **Tool Registry** (35 tools) connects AI Chat to every module: reads execute, **writes await your Approve/Edit/Reject** (HIGH-risk always). Plus **6 OpenRouter agents**, **2 model slots per provider**, **up to 7 agents** with distinct roles, a **debate-flow visibility toggle**, output-quality polish, and Settings → AI Tools / AI Chat. |
| **AllHaven 2.5** | 2026-06-11 | **AllHaven** | `v0.13.0` | **GUI-first install** (superseded by 2.6) — the terminal bootstrapped a **browser Setup Wizard** for OS/Docker checks, ports, `.env`, live progress, health, shortcut, open app. New entry points `./install.sh` and `npm run setup`. |
| **AllHaven 2.6** | 2026-06-11 | **AllHaven** | `v0.14.0` | **Terminal-only install** — install & start run **entirely in the terminal** again (live Docker/`pip`/`npm` progress); the browser wizard is now **opt-in** (`HAVEN_SETUP_WEB=1`), and the Docker check is faster (4s). The desktop shortcut starts services & opens Haven with no terminal. |
| **AllHaven 2.7** | 2026-06-12 | **AllHaven** | `v0.15.0` | **Premium UI polish + persistent model selection + per-section chat memory** — AI Chat now remembers your **model/agents, mode & thinking** across navigation/refresh (with availability fallback + clear warnings); each module **and each chat project/group** keeps its own **local, secret-redacted memory** the AI uses for relevance; **smooth micro-animations** that honor `prefers-reduced-motion`; polished Finance/Settings; and a fix for the session-check flash on every navigation. A frontend/UX release. |
| **AllHaven 2.8** | 2026-06-12 | **AllHaven** | `v0.16.0` | **Persistent AI memory** — auto-learns user context from chat (secret-safe, approval flow), injects it into all four chat modes, adds memory tools with human approval, a memory management page, and optional Supabase sync (migration `0007`). |
| **AllHaven 2.9** | 2026-06-13 | **AllHaven** | `v0.17.0` | **AI Workspace + Knowledge + finance reports + launch polish** — section-aware context packets, AI Knowledge document ingestion/search/retrieval with metadata-only storage for unsupported files, dedicated tool-call logging, 72 allowlisted tools, configurable Drive upload limits, monthly/weekly finance reports with archived/out-of-period records, local date/time answers, direct low-risk memory saves, a dedicated Approvals page, app-wide toast notifications, responsive UI across desktop/tablet/mobile, cleaner approval notifications, fresh-clone install guardrails, and a more direct conversational AI for coding and schedule management (migration `0008`). |
| **AllHaven 3.0** | 2026-06-13 | **AllHaven** | `v3.0.0` | **Launch-ready AI workspace** — app-wide layout polish, cleaner sidebar/topbar/dashboard, responsive shell refinements, AI Knowledge context available to every chat mode/model, language controls for Indonesian/English/Traditional Mandarin, dark/light theme and accent color preferences, in-app decision popups replacing browser `localhost says` dialogs, and language-aware local date/time answers. |
| **AllHaven 3.1** | 2026-06-13 | **AllHaven** | `v3.1.0` | **Expanded AI agents and settings UX** — raises multi-agent runs to 10 agents, adds Cursor AI, DeepSeek, and Qwen provider support, improves Debate prompts/final output, adds a searchable grouped model picker, and reorganizes Settings → AI Providers into health stats plus Direct/OpenRouter sections with honest provider verification. |
| **AllHaven 3.2** | 2026-06-13 | **AllHaven** | `v3.2.0` | **Repository hygiene and render skeletons** — removes local env files from the working tree, keeps clone-safe templates, adds app-wide and dashboard-specific skeleton loaders, and clarifies the CoreOS archive naming/semantic mapping. |
| **AllHaven 3.3** | 2026-06-13 | **AllHaven** | `v3.3.0` | **Routine planner and sidebar flow** — replaces Calendar with Routine, adds a polished date/time schedule planner, keeps calendar data compatible, and reorders the sidebar to Dashboard, AI Chat, Routine, Task, Finance, Notes, Approval. |
| **AllHaven 3.3.1** | 2026-06-13 | **AllHaven** | `v3.3.1` | **Local Routine UX polish** — keeps Routine local-first, adds icon/color/repeat/Pagi-Siang-Malam metadata, removes the goal field, keeps empty time lanes visible, and falls back to compatible local schedule endpoints. |
| **AllHaven 3.4** | 2026-06-13 | **AllHaven** | `v3.4.0` | **Voice, documents, Routine agenda, and local-first sync** — adds voice dictation in AI Chat, PDF/DOC/DOCX/text/code upload into AI Knowledge (DOCX parsing hardened against XXE with `defusedxml`), redesigns Routine as a lighter agenda/timeline, and broadens local-first Supabase mirroring across the workspace while keeping the local DB as the source of truth. |
| **AllHaven 3.5** | 2026-06-14 | **AllHaven** | `v3.5.0` | **AI routine generation and atomic save** — adds a "Generate with AI" flow to Routine that drafts realistic items for a Morning/Afternoon/Evening window for you to review and edit, saves reviewed drafts together atomically (an invalid item saves none), keeps generation honest (clear states when a provider is missing or disabled, never saves on its own), adds a Routine sync-status card, and refactors the routines page into focused components. |
| **AllHaven 3.6** | 2026-06-17 | **AllHaven** | `v3.6.0` | **Privacy cleanup** — housekeeping release that removes a personal local-path identifier from the in-repo development notes so the project ships clean as a personal project. No application code, API, or behavior changes. |
| **AllHaven 3.7** | 2026-06-19 | **AllHaven** | `v3.7.0` | **Two-way Postgres⇄Supabase sync + mobile-on-Supabase** — desktop stays local-first Postgres with a new two-way incremental sync engine (LWW + tombstones + visible status); mobile talks directly to Supabase (Auth + RLS) for Tasks/Notes/Finance/Calendar/Routines/Automations/Weather; Supabase Auth provisioning + "Connect to Supabase"; migrations 0010–0015 (deleted_at, supabase_user_id, updated_at trigger, RLS + workspace_members hardening, sync_state); login timeout fix; checklist soft-delete for correct sync. |
| **AllHaven 3.8** | 2026-06-19 | **AllHaven** | `v3.8.0` | **Mobile full release, unified accounts, performance & Weather removal** — a stability audit (routine recurrence expansion + further bug fixes), unified desktop/mobile accounts, performance work, and the start of removing Weather from the product scope. |
| **AllHaven 3.9** | 2026-06-20 | **AllHaven** | `v3.9.0` | **AI pipeline overhaul + cross-device approvals** — a deterministic intent router (finance-first, so money is never stored as memory; robust Indonesian/IDR parsing), proposal lifecycle with two-way sync (FAILED/NEEDS_EDIT, no double-execution), cross-device approvals (mobile and desktop act on the same pending list), readable proposal cards, plus a desktop CSS-on-update fix and standalone register. |
| **AllHaven 4.0** | 2026-06-20 | **AllHaven** | `v4.0.0` | **Full Mobile Parity + Tailscale Bridge + release-grade stability** — every active desktop module is reachable on mobile with honest setup-required states (no "use the desktop app"); a **Tailscale Desktop Bridge** for desktop-local Ollama/n8n (Funnel off by default) and a runtime **Backend Bridge** to point the installed app at your desktop with no rebuild; deployment profiles, end-to-end version visibility, Weather removal; an idempotent **self-healing installer** (native-Postgres detection, broken-venv repair, venv Alembic) + `scripts/doctor.sh`; backend 473 tests pass. |
| **AllHaven 4.1** | 2026-06-28 | **AllHaven** | `v4.1.0` | **Dashboard charts, editable Notes, cleaner AI Memory, and mobile login clarity** — restores visible finance cashflow charts, adds edit/save support for existing Notes, improves AI Memory handling for current single-value facts, suppresses noisy insult-like auto-memory, surfaces real Supabase mobile-login failures, upgrades Next.js to 15.5.19, and tightens local CORS for localhost/LAN/Tailscale/Capacitor origins. |
| **⭐ AllHaven 4.2** | 2026-07-02 | **AllHaven** | `v4.2.0` | **Aurora Glass UI, AI-brain completion & security hardening** — restyles every page and component on the shared Aurora Glass token/primitive system (visual-only); completes the v4.0 AI-brain audit (smalltalk short-circuit, reply quality gate, ROUTINE intent, Indonesian "dapat" income parsing, typed human-readable approval previews); restores desktop voice input and the memory soft-delete migration; stabilizes AI memory recall/editing and knowledge upload; hardens security (private-integration SSRF guard, API docs hidden outside local mode, protected Drive config endpoint); makes the launcher robust against stale ports; requires Supabase migrations 0018–0020 for cross-device approval idempotency. |

<sub>⭐ = current release. Dates reflect each version's build/release during the project's initial development sprint.</sub>

## 🌱 How the two branches relate

Each archive folder is a complete, standalone snapshot you can open and run on
its own; the latest (`AllHaven 4.2`) keeps its own `CHANGELOG.md`, `VERSION`, and
`docs/`/`docs/v4/` release notes inside it. New releases add the next folder here, while
[`main`](../../tree/main) is fast-forwarded to the same version.

---

<div align="center">

**© 2026 Joshua Setiawan.** All rights reserved.

<sub>AllHaven Command Center — crafted by <b>Joshua Setiawan</b></sub>

</div>
