# AllHaven — Version Archive (`master`)

This branch records **every version of the project**, one self-contained folder per
release, named `AllHaven <version>` from oldest to newest. The **latest version
also lives on the [`main`](../../tree/main) branch** as the runnable app at root.

> Numbering: `0.1 → 0.9`, then rolls over to `1.0 → 1.6` (so the folders sort and
> read naturally). A new big update adds the next folder (`AllHaven 1.7`, …).

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
| **AllHaven 1.6** | **AllHaven** | **Current.** **Calculator** & **Clock** (stopwatch/timer/alarm) modules, **Thinking Mode** (Fast/Balance/Thinking/Deep) separate from chat mode, chat modes simplified to Parallel/Debate/Reasoning, and **vision routing** (images go only to vision-capable models; others say so honestly). Internally semantic `v0.5.0`. |

## How the two branches relate

- **`main`** — only the **latest** version (`AllHaven 1.6`), flat at the repo root, ready to run/deploy.
- **`master`** (this branch) — the **full archive**: every version frozen in its own folder.

Each version folder is a complete snapshot you can open and run on its own; the
latest one (`AllHaven 1.6`) keeps its own detailed `CHANGELOG.md`, `VERSION`, and
`docs/releases/` inside it.
