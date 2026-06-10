# AllHaven — Version Archive (`master`)

This branch records **every version of the project**, one self-contained folder per
release, named `AllHaven <version>` from oldest to newest. The **latest version
also lives on the [`main`](../../tree/main) branch** as the runnable app at root.

> Numbering: `0.1 → 0.9`, `1.0 → 1.9`, then `2.0` onward (so the folders sort and
> read naturally). A new update adds the next folder (`AllHaven 2.1`, …).

## Versions & what each update introduced

| Version | Era | What changed in this update |
|--------|-----|------------------------------|
| **AllHaven 0.1** | CoreOS | Initial base — FastAPI + PostgreSQL backend, Next.js + TS + Tailwind frontend, auth, and the first modules (Tasks, Notes, Finance). |
| **AllHaven 0.2** | CoreOS | UI layer — app layout (PageHeader, nav) and a reusable UI kit (Avatar, BarChart, IconButton, Select, Tabs, Toggle) + user preferences. |
| **AllHaven 0.3** | CoreOS | AI provider system — provider router, provider registry, encrypted secrets, integration config service + schemas (migration `0002`). |
| **AllHaven 0.4** | CoreOS | New module pages (Drive, Calendar, Weather, Automations) + task checklists (migration `0003`) + the Blackbox provider. |
| **AllHaven 0.5** | CoreOS | Google OAuth foundation (router + service + card) and Ollama provider tests. |
| **AllHaven 0.6** | CoreOS | Per-workspace **AI policy** — allow/deny external AI providers. |
| **AllHaven 0.7** | CoreOS | Command palette (⌘K) for fast navigation/search. |
| **AllHaven 0.8** | CoreOS | One-command setup/run helper script. |
| **AllHaven 0.9** | CoreOS | Stability fixes and refinements (no new surface). |
| **AllHaven 1.0** | CoreOS | **Multi-agent chat + module backends** — concurrent agents and Drive/Calendar/Weather/Automations APIs (migration `0004`). |
| **AllHaven 1.1** | CoreOS | Session memory / project documentation. |
| **AllHaven 1.2** | CoreOS | **Production deployment** — Dockerfiles, prod compose with Caddy HTTPS, deploy guide. |
| **AllHaven 1.3** | CoreOS | Cross-OS run scripts + local-setup and release docs. |
| **AllHaven 1.4** | **AllHaven** | Rebrand to AllHaven + responsive UI, **multi-agent Debate** mode, and the **Reasoning Quality Layer** (Analyst → Critic → Synthesizer with grounded, verified reasoning). Internally semantic `v0.3.0`. |
| **AllHaven 1.5** | **AllHaven** | **Image input (vision)** — attach images and have agents respond to them — plus **Markdown-rendered chat output** so replies read cleanly. Internally semantic `v0.4.0`. |
| **AllHaven 1.6** | **AllHaven** | **Calculator** & **Clock** (stopwatch/timer/alarm) modules, **Thinking Mode** (Fast/Balance/Thinking/Deep) separate from chat mode, chat modes simplified to Parallel/Debate/Reasoning, and **vision routing** (images go only to vision-capable models; others say so honestly). Internally semantic `v0.5.0`. |
| **AllHaven 1.7** | **AllHaven** | When a vision-capable provider gets an image but the chosen **model** is text-only, the raw API error is now an honest **"this model can't read images — pick a vision model"** status. Internally semantic `v0.5.1`. |
| **AllHaven 1.8** | **AllHaven** | **Launch hardening** — HTTP security headers (backend + frontend CSP), safe Drive downloads (attachment + neutralized active types), and dependency patches (Next 14.2.35, postcss 8.5.15). Full audit in `LAUNCH_SECURITY_REPORT.md`. Internally semantic `v0.6.0`. |
| **AllHaven 1.9** | **AllHaven** | **Public-launch auth** — HttpOnly **cookie sessions** (hashed server-side, rotation via refresh, revocation on logout), **CSRF** double-submit, `/auth/*` **rate limiting**, and a production **SECRET_KEY guard**. No auth token in localStorage anymore. Internally semantic `v0.7.0`. |
| **AllHaven 2.0** | **AllHaven** | **Current.** **Live n8n workflows** in Automations — list your real workflows from the connected n8n, **activate/deactivate**, and **open in n8n** (API key stays server-side; honest states when n8n isn't ready). Internally semantic `v0.8.0`. |

## How the two branches relate

- **`main`** — only the **latest** version (`AllHaven 2.0`), flat at the repo root, ready to run/deploy.
- **`master`** (this branch) — the **full archive**: every version frozen in its own folder.

Each version folder is a complete snapshot you can open and run on its own; the
latest one (`AllHaven 1.7`) keeps its own detailed `CHANGELOG.md`, `VERSION`, and
`docs/releases/` inside it.
