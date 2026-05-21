# Handoff: AllHaven — "Aurora Glass" Redesign

## Overview
A full dark‑theme visual redesign of the **AllHaven Command Center** — a local‑first, human‑in‑the‑loop AI workspace (multi‑agent chat, finance, tasks, notes, routine, approvals, and utility modules). The redesign is a single interactive prototype covering **Login + 14 screens + a 6‑tab Settings console**, all in one cohesive visual language called **Aurora Glass**: near‑black navy canvas, frosted‑glass panels, luminous cyan→violet accents, and slow‑drifting "aurora" glow blobs.

This handoff documents the design precisely enough to rebuild it in a real codebase without having been in the design conversation.

## About the Design Files
The files in this bundle are **design references authored in HTML/CSS/JS** — a prototype that demonstrates the intended look, layout, and interaction. **They are not production code to copy verbatim.**

The AllHaven app is a **Next.js / React + TypeScript + Tailwind** project (App Router, `frontend/app/dashboard/*`, component library under `frontend/components/ui/*`). The task is to **recreate these designs in that existing environment**, using its established patterns — Tailwind tokens, the `Card`/`Button`/`Toggle`/`Tabs`/`Badge`/`Select`/`Input` primitives, Lucide icons, and the existing API/data layer. Do **not** ship the prototype's inline styles or its bespoke render runtime. Map the Aurora Glass tokens below onto the Tailwind theme (extend `tailwind.config` colors + add the glass utilities), then rebuild each screen with real components and real data.

If you are starting fresh with no environment, React + Tailwind is the recommended target to match the source repo.

## Fidelity
**High‑fidelity (hifi).** Final colors, typography, spacing, radii, shadows, and interaction states are all specified. Rebuild the UI pixel‑faithfully using the codebase's component library — treat the hex values, radii, and type sizes below as the source of truth. The prototype uses **mock/sample data** (numbers, transactions, chat messages); wire the real data layer in its place.

---

## Design Tokens

### Color — surfaces & text
| Token | Value | Use |
|---|---|---|
| `bg/base` | `#06070E` | App + login canvas (near‑black navy) |
| `bg/base-alt` | `#0A0C16` | Inner ring of progress dial, opaque wells |
| `surface/glass` | `linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.018))` | Primary card fill |
| `surface/glass-hi` | `rgba(255,255,255,0.03)` | Nested tiles / inputs |
| `border/glass` | `rgba(255,255,255,0.09)` | Card & input border |
| `border/glass-soft` | `rgba(255,255,255,0.07)` | Dividers, section rules |
| `text/primary` | `#EAF2FF` | Headings, key values |
| `text/secondary` | `#9AA6C4` | Body copy |
| `text/muted` | `#7C86A4` | Labels, meta |
| `text/faint` | `#5D6788` | Timestamps, axis ticks |

### Color — accents & status
| Token | Value | Use |
|---|---|---|
| `accent/cyan-hi` | `#7FF7F2` | Primary accent text/icon |
| `accent/cyan` | `#2DE1E1` | Accent mid (bars, gradients) |
| `accent/violet` | `#A78BFA` | Secondary accent |
| `accent/violet-hi` | `#C4B5FD` | Violet text/icon |
| `accent/violet-deep` | `#8B5CF6` | Violet bar base |
| `gradient/primary` | `linear-gradient(135deg, #6BF5F0, #A78BFA)` | Buttons, logo, avatar, active nav icon |
| `gradient/primary-alt` | `linear-gradient(135deg, #7FF7F2, #A78BFA)` | Logo tile, icon chips |
| `status/success` | dot `#34D399`, text `#5EEBB0` | Online / approved |
| `status/warning` | `#FCD34D` (text), `#F5B544` | Pending / configured‑external / MVP |
| `status/danger` | `#FF9494` (text), border `rgba(255,148,148,0.3)` | High risk / expense / reject |
| `glow/magenta` | `#E24DB8` | Third aurora blob only |

### Glass card recipe (canonical)
```
border-radius: 20px;               /* cards 18–20, tiles 16, buttons 11–14, pills 9999 */
border: 1px solid rgba(255,255,255,0.09);
background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.018));
box-shadow: 0 24px 60px -24px rgba(0,0,0,0.72), inset 0 1px 0 rgba(255,255,255,0.08);
backdrop-filter: blur(20px);       /* 18–20 on cards, 16 on header/top bars */
```
Accent/emphasis cards swap the border to `rgba(45,225,225,0.22)` and the fill to `linear-gradient(120deg, rgba(45,225,225,0.08), rgba(167,139,250,0.05))`.

### Primary button recipe
```
background: linear-gradient(135deg, #6BF5F0, #A78BFA);
color: #0A1512; font-weight: 600;
box-shadow: 0 14px 30px -12px rgba(45,225,225,0.8), inset 0 1px 0 rgba(255,255,255,0.3);
border-radius: 12px;  hover: filter: brightness(1.06);
```
Secondary button: `border:1px solid rgba(255,255,255,0.1); background:rgba(255,255,255,0.04); color:#EAF2FF`.

### Toggle (switch) recipe
Track 44×24 (or 48×26), `border-radius:9999px`, `padding:2px`. ON = `linear-gradient(90deg,#2DE1E1,#A78BFA)` + `box-shadow:0 0 14px rgba(45,225,225,0.3)`, knob 20×20 white pushed right (`margin-left:auto`). OFF = track `rgba(255,255,255,0.1)`, knob `#8A93A6` left.

### Typography
- **Font family:** `Geist` (weights 300–700); **mono:** `Geist Mono`; fallback `Inter, system-ui, sans-serif`. Mono is used for labels/eyebrows, metrics, timestamps, code‑like chips.
- **Scale (px):** page H1 30 / 600 / ‑0.02em · greeting 34 / 600 · balance hero 36 / 600 / ‑0.025em · section H2 15 / 600 · body 13.5–14 · meta 12–12.5 · label‑mono 10–11 uppercase `letter-spacing:0.08–0.2em` · clock display 64 mono.
- `-webkit-font-smoothing: antialiased`.

### Radii / spacing
Cards 18–20px · tiles/stat cards 16px · buttons 11–14px · icon tiles 9–13px · pills/avatars 9999px. Screen padding **26px**. Card padding 18–24px. Grid gaps 14–22px.

### Aurora background (motion)
Three absolutely‑positioned radial‑gradient circles behind content, `filter: blur(46–70px)`, low opacity. Keyframes (respect `prefers-reduced-motion`):
```
@keyframes auroraDrift { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(3%,2%) scale(1.06)} }
@keyframes floatY      { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-6px)} }
@keyframes pulseGlow   { 0%,100%{opacity:.45} 50%{opacity:1} }   /* live status dots */
```
Blob palette: cyan `rgba(45,225,225,0.22)`, violet `rgba(167,139,250,0.18)`, magenta `rgba(226,77,184,0.10)`. Durations 18–26s, one reversed. On login the opacities are a touch higher (0.26 / 0.22 / 0.14).

### Icons
**Lucide** throughout (currently via CDN; use `lucide-react` in the app). Key glyphs: shield‑check (brand), layout‑dashboard, bot, calendar‑days, list‑todo, wallet, sticky‑note, clipboard‑check, calculator, clock, hard‑drive, workflow, book‑open‑check, brain, settings, sparkles, plus, search, bell, trending‑up, arrow‑up‑right, plug, cpu, database, cloud, globe, wrench, send, terminal, palette.

---

## App shell (persists across all in‑app screens)

**Layout:** full‑height flex row. **Sidebar 280px** (fixed) + **main column** (flex‑1, `position:relative`, aurora layer behind, content `z-index:1`).

### Sidebar (280px)
- Fill `linear-gradient(180deg, rgba(14,16,30,0.72), rgba(8,9,16,0.72))`, `backdrop-filter:blur(18px)`, right border `rgba(255,255,255,0.07)`, own vertical scroll.
- **Brand row:** 42px gradient tile (shield‑check) + "All**Haven**" (the "Haven" is gradient‑clipped cyan→violet text) + mono "v4.1.0".
- **"New Command"** primary gradient button (full width, 46px).
- **Nav groups:** eyebrow "Workspace" then Dashboard, AI Chat, Routine, Task, Finance, Notes, Approval; eyebrow "Modules" then Calculator, Clock, Drive (MVP), Automations (MVP), AI Knowledge (NEW), AI Memory (NEW); divider; Settings. NEW badges are cyan; MVP badges are neutral.
- **Nav item:** 44px min‑height, gap‑12, 32px icon tile + label. **Active state:** row `background:linear-gradient(90deg, rgba(45,225,225,0.18), rgba(167,139,250,0.10))`, `border:1px solid rgba(45,225,225,0.32)`, `box-shadow:0 0 26px rgba(45,225,225,0.22)`; icon tile becomes the primary gradient with dark glyph; label `#EAF2FF` weight 600. Inactive label `#9AA6C4`, icon tile `rgba(255,255,255,0.035)` border `rgba(255,255,255,0.08)`.
- **Footer:** user card (28–34px gradient avatar "JS", name + email) + Sign Out (hover tints red `#FF9494`).

### Top bar (66px)
`background:rgba(6,7,14,0.55)`, `backdrop-filter:blur(16px)`, bottom border `rgba(255,255,255,0.07)`. Left: pill search field (max 560px) with search icon, placeholder "Search tasks, notes, pages…", `⌘K` kbd. Right: **"Local AI · Online"** success pill with pulsing dot, bell (with gradient "3" badge), settings icon, 38px gradient avatar.

---

## Screens / Views

> All screens sit inside the shell's scrolling content area (`padding:26px`) except **AI Chat**, which is full‑height two‑pane with its own internal scroll regions.

### 1. Login (pre‑auth, full‑screen)
- Centered card, **max‑width 440px**, on the aurora canvas (blobs slightly brighter).
- **Gradient hairline frame:** outer `border-radius:26px` wrapper with `padding:1px` and a `linear-gradient(160deg, rgba(127,247,242,0.5), rgba(255,255,255,0.06) 42%, rgba(167,139,250,0.4))`; inner panel `border-radius:25px`, fill `linear-gradient(180deg, rgba(18,20,34,0.86), rgba(10,11,20,0.92))`, `blur(22px)`, padding 34/32/30.
- 52px gradient logo tile (shield‑check) → H1 "AllHaven Command Center" (22/600) → mono eyebrow "YOUR PRIVATE AI WORKSPACE".
- **Access / Register** segmented control (Access active).
- Fields: "Command ID (Email)" with at‑sign icon (sample `identity@allhaven.ai`); "Access Key" with key icon + eye toggle (masked dots). Field shell 46px, `border-radius:12px`, border `rgba(255,255,255,0.1)`, fill `rgba(255,255,255,0.035)`.
- **"Access Command Center"** primary gradient button (48px) → arrow‑right. Click authenticates → app opens on Dashboard.
- "Secure bypass" divider → **Biometric** / **Hardware Key** buttons.
- Footer: security note with cyan dot + mono "AllHaven Executive Interface v4.1.0".

### 2. Dashboard
- **Header:** version pills (v4.1.0 cyan, Local‑first neutral) → greeting "Good morning, **Joshua**" (Joshua gradient‑clipped) → subtitle. Right actions: Routine, Approvals (secondary), **AI Chat** (primary) — all navigate.
- **2fr / 1fr grid, gap 20.**
  - **Left col:** *Workspace Snapshot* card (sparkles chip + three stat tiles: Open tasks **7**, Notes **12**, Txns/month **34**); *Monthly cashflow* card (balance **Rp 24.850.000** with cyan text‑glow, +18% success chip, 5 gradient bars W1–W5 with gridlines — W2 is the violet bar, rest cyan — Income `#5EEBB0` / Expense `#FF9494` chips); *Human‑in‑the‑loop* accent card (shield, links to AI Chat).
  - **Right col:** *Pending tasks* list (5 rows, priority pills High/Medium/Low, "View all" → Tasks); *Integration status* list (Ollama, Supabase, OpenAI/GPT, Claude, Tailscale Bridge = Online/Configured; n8n = Not configured) with glowing status dots, "Manage integrations" → Settings.

### 3. AI Chat (flagship, full‑height two‑pane)
- **Left rail 264px:** "Conversations" + new‑chat gradient button, search field, grouped list (Today / Yesterday). Active conversation = cyan accent card.
- **Right pane (flex‑1):**
  - **Header:** sparkles tile + title "Monthly finance review" + mono "AllHaven Multi‑Agent · honest status" + "Finance memory" violet chip. **Mode segmented control**: Parallel (active) / Debate / Reasoning. Status chips: "Local AI" (success), "External AI" (warning). **Agents row**: selected chips (check icon, cyan glow) Claude / GPT‑4o / Ollama, unselected Gemini, dashed "+ Add".
  - **Thread (scrolls):** user bubble (right‑aligned, cyan gradient, `border-radius:16px 16px 4px 16px`); assistant bubbles per‑agent (mono agent label, left‑aligned `4px 16px 16px 16px`, tool/memory chips like "used memory", "read finance_summary"); a **pending‑approval tool card** (`create_budget_alert`, warning border, Approve/Edit/Reject); a **"Final answer"** synthesis card (cyan accent, crown icon).
  - **Composer:** rounded field with paperclip, "Message your agents…", mic, gradient send button; helper "AllHaven never fabricates AI output · risky writes require approval".

### 4. Finance
- Header "Finance" + "Cashflow report — July 2026" + actions Refresh / Categories / **New transaction**.
- **Controls row:** Monthly/Weekly segmented, month stepper "‹ July 2026 ›", "Current".
- **Three stat cards:** Income **Rp 41.200.000** (`#5EEBB0`, arrow‑down‑left), Expense **Rp 16.350.000** (`#FF9494`, arrow‑up‑right), Balance **Rp 24.850.000** (cyan accent card, wallet).
- **2fr/1fr grid:** *Transactions* list (5 rows, colored in/out icon tiles, category + date mono, signed amounts) · *Weekly spend* bar chart (5 bars, W2 violet) + disclaimer.

### 5. Tasks ("Active Commands")
- Header + **Create Task** primary button. Accent info banner about command checklists (Dismiss).
- **Filter tabs:** All 12 (active) / Todo 7 / In Progress 2 / Done 3.
- **Task rows** (glass cards): checkbox (or filled green check when done), title, meta chips — priority pill (High `#FF9494` / Medium `#FCD34D` / Low neutral), status (In Progress cyan dot / Todo / Done), optional due date, "Checklist n/m" link; right side Done + trash. Completed row is line‑through + dimmed with Reopen.
- **Three stat cards:** Total 12 / In progress 2 (cyan) / Completed 3 (green).

### 6. Notes
- Header + **New note**. Search field + category chips (All / Work / Personal / Ideas).
- **CSS `columns:3` masonry**, `column-gap:16px`, cards `break-inside:avoid`. First card is **Pinned** (cyan accent, pin eyebrow). Each: icon tile, title, 2–3‑line preview, category pill + relative time. Categories tint their pill/icon (Work=cyan, Ideas=violet, Personal=green).

### 7. Routine
- Header "Routine" + "Tuesday, 1 July · your day at a glance" + date stepper + **Add block**.
- **2fr/1fr grid:** *Today's timeline* card — vertical rail with time labels (mono) and color‑dotted blocks (Health=green, Focus=cyan accent+glow "in progress", Meeting=violet, generic=neutral). Right col: **progress dial** (conic‑gradient ring `#2DE1E1 0–68%`, inner dark disc, "68% · 4/6 blocks") + *Habits* card (green check tiles + "flame" streaks; one pending unchecked).

### 8. Approvals
- Header "Approvals" + **"3 pending"** warning count + subtitle "Nothing runs until you approve." Filter tabs Pending/Approved/Rejected.
- **Approval cards:** left risk‑tinted icon tile, action name + **risk badge** (High risk red / Medium amber), plain‑language description, provenance chips (agent · local/external, relative time), **Approve** (primary) / **Edit** / **Reject** (red). First card `delete_transactions` = High risk (red border). Plus a dimmed **approved** history row.

### 9. Settings — **6‑tab console**
Header "Command Center Settings" + subtitle "…credentials are stored securely server‑side." + "AllHaven v4.1.0" chip. **Tab bar** (underline style, active tab = cyan gradient fill, `border-radius:11px 11px 0 0`): counts shown as small pills.
- **Connected Tools (7):** *Backend Bridge* card (Connected, latency, Reconnect) + *Desktop Bridge* (Paired, Manage) + **grid of integration cards** (PostgreSQL, Ollama, Supabase, Google Calendar = Online; n8n = Not set up; Drive = MVP) — each with icon, status pill, description, and a **Configure** button (cyan outline).
- **AI Providers (16):** four stat cards (Configured 9/16, Online 2, Enabled 6, Selectable slots 4) → **external‑providers** accent card (toggle + Default provider select) → **Direct model agents** grid (Ollama, OpenAI·GPT, Anthropic·Claude, Gemini, Cursor, DeepSeek — each: icon, name, enable toggle, status line, **Configure**) → **OpenRouter model agents** grid (OpenRouter 1–3 shown, "6 agents").
- **AI Tools:** list of callable tools (read_finance_summary, update_memory, create_task, send_email, web_search) with risk badge (Safe / Approval / High risk) + enable toggle.
- **AI Chat:** *Chat behavior* (default mode segmented, Stream responses toggle, Use AI memory toggle) + *Generation* (Temperature slider 0.7, System prompt well).
- **Privacy & Safety:** *Profile* card (avatar + Owner Access, Full name, Workspace name, Primary email, Save) + *Appearance* (Language, Theme selects; **Color nuance** accent picker Aurora/Mint/Magenta/Amber; Glassmorphism + Compact density toggles) + *AI privacy & safety* accent card (bullets).
- **System Control:** three metric cards (CPU 18%, Memory 4.2/16 GB, Uptime 14d 06h) with progress bars + *Service control* list (Backend API, Ollama, Postgres = healthy + Restart; n8n = stopped + Start).

### 10–15. Modules
- **Calculator:** glass calculator (dark result well, 4‑col keypad; operators cyan, "=" primary gradient) + **Currency** converter (USD→IDR) + **Recent** mono list.
- **Clock:** large cyan‑glow mono time (Jakarta/WIB) + date; **4 world‑clock** tiles (London/New York/Tokyo/Sydney with offsets); **Timer** (24:59, Pause/Reset) + **Stopwatch** (Start/Lap) cards.
- **Drive (MVP):** header + Upload; storage meter (12/50 GB gradient bar, 248 files · 14 folders); 4‑col grid of folder/file tiles (colored icon tiles, name, size/updated).
- **Automations (MVP):** header + New flow; flow rows — icon tile, name, "trigger → action" description, Active/Paused status, enable toggle (one paused/dimmed).
- **AI Knowledge (NEW):** header + Add source; 3‑col grid of source cards (Company handbook, Client contracts = Indexed; Product docs site = Indexing 64%) with chunk/type mono meta.
- **AI Memory (NEW):** header + Add fact; two grouped cards (Finance, Preferences) each a list of remembered facts with an "×" (forget) affordance.

---

## Interactions & Behavior
- **Auth gate:** `authed=false` shows Login; the Access button sets `authed=true` and routes to Dashboard. Sign Out returns to Login.
- **Primary navigation:** every sidebar item (and several in‑content links/buttons carrying a target, e.g. "View all" → Tasks, "AI Chat" → ai, "Manage integrations" → Settings) sets the current `page`; the content area swaps to that screen and the active nav styling updates.
- **Settings sub‑tabs:** independent `stab` state switches the 6 panels; active tab restyles to the cyan gradient underline‑pill. Default tab = **Connected Tools** (`tools`).
- **Active‑state syncing:** after any navigation, nav rows and settings tabs are restyled and Lucide icons re‑hydrated (in React this is just conditional `className`s + `lucide-react`, no manual DOM pass).
- **Hover:** primary buttons `filter:brightness(1.06)`; nav/rows lift to a faint translucent fill; Sign Out tints red.
- **Live accents:** status dots pulse (`pulseGlow` 1.6–2s); aurora blobs drift 18–26s. Honor `prefers-reduced-motion: reduce` by disabling these.
- **Prototype‑only (wire to real logic on rebuild):** calculator keypad, toggles, sliders, timers, filter tabs, and approve/reject buttons are visual — implement real handlers/state and data.

## State Management
- `authed: boolean` — gates Login vs. app shell.
- `page: enum` — `dashboard | ai | finance | tasks | notes | routine | approval | settings | calculator | clock | drive | automations | knowledge | memory`. In Next.js this is naturally the **route** (`/dashboard`, `/dashboard/ai`, …) rather than local state.
- `stab: enum` — Settings tab: `tools | ai | ai-tools | ai-chat | privacy | system` (URL query or nested route).
- Screen data (tasks, transactions, providers, integrations, conversations, memory facts) currently mocked — replace with the app's API hooks. Toggles/seles (external‑AI policy, default provider, appearance prefs) map to the existing settings/policy endpoints.

## Assets
- **Icons:** Lucide (swap CDN → `lucide-react`).
- **Fonts:** Geist + Geist Mono via Google Fonts (or `geist` npm package / `next/font`).
- **No raster images** — every surface is CSS (gradients, blur, shadow). No exported image assets required. Avatar/logo are gradient tiles with initials/glyphs.
- Aurora blobs, glass, and glows are pure CSS — port them as Tailwind utilities/`@layer` components.

## Files
- `AllHaven Aurora.dc.html` — the complete interactive prototype (Login + 14 screens + 6 Settings tabs). Primary reference.
- `AllHaven Dashboard.dc.html` — earlier exploration board: a faithful rebuild of the *current* dashboard plus three visual directions (1a Aurora Glass — the chosen one, 1b Precision HUD, 1c Editorial Calm). Useful only as rationale/context for why Aurora Glass was selected.
- `support.js` — the prototype's render runtime. **Reference only — do not port.** It exists so the `.dc.html` files open in a browser; it is not part of the design.

### How to preview the prototype
Open `AllHaven Aurora.dc.html` in a browser (it loads `support.js` beside it). Click **Access Command Center**, then use the sidebar to move between screens and the Settings tab bar to see all six panels.
