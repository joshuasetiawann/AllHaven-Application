# AllHaven — Mobile QA Report

- **App version:** v3.8.0
- **Date:** 2026-06-19
- **Build:** Capacitor APK, `BUILD_TARGET=mobile`, `NEXT_PUBLIC_AUTH_MODE=bearer`, `NEXT_PUBLIC_DATA_MODE=supabase`, static export → `out/` (webDir).
- **Connectivity:** Supabase directly for data; backend (AI/Drive/Settings) reachable only over Tailscale.
- **Method:** Static review of the responsive layout system + the mobile data path. Breakpoint behavior is reasoned from the Tailwind classes and layout structure, not captured as device screenshots. Where I could not visually confirm, it is called out as **static-only**.

## 1. Mobile data path — works without the backend

The phone talks straight to Supabase for the core modules, so the app is usable offline-of-backend for everything that matters day to day:

| Module | Mobile | How |
|--------|--------|-----|
| Auth (login/register) | ✅ | Backend provision (first time) → Supabase Auth bearer. |
| Tasks (+ checklist, complete) | ✅ | Supabase `tasks` / `task_checklist_items`, client-minted ids. |
| Notes | ✅ | Supabase `notes`. |
| Finance | ✅ | Supabase `categories` / `transactions`; summary aggregated client-side. |
| Routines (+ all settings, recurrence) | ✅ | Supabase `calendar_events`; recurrence expanded client-side. |
| Automations | ✅ | Supabase; n8n control is REST-only. |
| Calculator / Clock | ✅ | Pure client-side. |
| Calendar | ✅ | Redirects to Routines. |
| AI Chat / Approvals / Memory / Knowledge / Drive / Settings / Integrations / AI Providers | 🔌 backend-only | Work only when the backend is reachable over Tailscale; otherwise fast-fail at 6 s. |

### Write-path correctness (the class of bugs that plagued mobile)

- **Client-minted ids.** Supabase `id` columns have no DB default (models use a Python-side `uuid4` default, not `server_default`), so every mobile insert mints a UUID via `newRow()`. This fixed the "id not full constraint" write failures across notes/finance/routines/tasks.
- **Scope on every row.** `newRow()` also stamps `workspace_id` + `created_by`; if either is missing it throws a clear `NOT_AUTHENTICATED` (401) instead of letting RLS reject a silent bad row.
- **Checklist split.** Task create writes `task_checklist_items` separately rather than a non-existent `tasks.checklist` column.

## 2. REST-only modules on mobile — current UX gap

When the backend is unreachable, the REST-only modules (AI Chat, Drive, Knowledge upload, Settings, Memory suggestions, Routine Generate) currently *look* available and then silently time out at 6 s. The timeout is mobile-aware (6 s on bearer vs 20 s on desktop) so the app never hangs — but there is no upfront "this needs the desktop app / a backend connection" message.

- **Severity:** Medium (UX clarity, not data loss).
- **Recommended hardening (deferred, no backend needed):** add explicit banners/guards on those screens when `DATA_MODE=supabase` and the backend is unreachable. Tracked in `FULL_FEATURE_AUDIT_REPORT.md` → Known gaps #3.

## 3. Responsive layout review (static)

**Shell.** `AppShell` renders a persistent rail on `md+` and a **drawer** below `md` (`hidden … md:block` for the rail; `md:hidden` overlay drawer that closes on route change). The main content is:

```
mx-auto w-full max-w-[1480px] overflow-x-hidden px-3 py-4 sm:px-5 sm:py-5 lg:px-8 lg:py-7
```

`w-full` + `max-w` + `overflow-x-hidden` means **no horizontal overflow** at narrow widths — the documented risk at 375 px is structurally prevented.

**Progressive enhancement.** Heavy `sm:` usage (≈257 occurrences) with lighter `lg:`/`xl:` — i.e. mobile-first single-column layouts that expand to multi-column on larger screens (e.g. Notes is a single reader on mobile via a `mobileReader` toggle, two-pane `lg:grid-cols-[360px_1fr]` on desktop).

**Fixed widths audited.** Every raw `w-[NNNpx]` is either `max-w` (the 1480 px content cap), behind a `sm:`/`lg:` prefix (e.g. finance date input `sm:w-[132px]`, with `min-w-0 flex-1` on mobile), or inside an `overflow-x-hidden`/horizontally-scrollable container (loading skeleton). No unconstrained wide element reaches the 375 px viewport.

**Mobile declutter.** Dense screens were thinned for mobile in commit `326d3bf` (responsive only; desktop layout unchanged).

### Breakpoint expectations

| Width | Class of device | Expected layout | Confidence |
|-------|-----------------|-----------------|------------|
| 375 px | iPhone SE / small Android | Single column, drawer nav, no h-scroll | High (structure) — static-only |
| 430 px | Large phone | Single column, slightly roomier paddings | High (structure) — static-only |
| 768 px | Tablet / `md` | Persistent rail appears, 1–2 column content | High (structure) — static-only |
| 1280 px | Laptop / `lg` | Multi-column, wider gutters (`lg:px-8`) | High — matches desktop build |
| 1440 px | Desktop / `xl` | Content capped at 1480 px, centered | High — matches desktop build |

> **Static-only caveat:** these are reasoned from the layout classes and the clean production build, not from on-device screenshots. A device/emulator pass (or Playwright viewport screenshots) is the remaining step to turn "High (structure)" into "Verified".

## 4. Verification performed

- `next build` (web/desktop target): clean — all 21 routes prerendered, lint + types pass.
- `tsc --noEmit`: 0 errors.
- Dev server: `layout.css` → HTTP 200 (70 KB); `/dashboard/routines` → HTTP 200.
- The mobile APK build path (`build:mobile`) is unchanged by this cycle's fixes (the fixes are in shared data-layer + routine code that both targets compile).

## 5. Open follow-ups for mobile

1. On-device/emulator visual pass at 375 / 430 / 768 px (turn static review into verified).
2. "Requires desktop / backend" banners on REST-only screens (Audit gap #3).
3. Routine alarms (persistence + scheduler + mobile delivery) — backend phase (Audit gaps #1/#2).
