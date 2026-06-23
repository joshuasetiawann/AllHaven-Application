# Haven — Desktop Setup (beginner guide)

This guide is for non-technical users. You only need to **clone the repo** and
**open one file**. The setup wizard does the rest.

---

## 1. Install (fresh) — then run with `./allhaven.sh`

| Step | Command | Notes |
|------|---------|-------|
| **Fresh install** (Linux/macOS) | `./install.sh` | Installs in the terminal: tools, `.env`, deps, migrations, then starts + opens the app. |
| **Fresh install** (Windows) | `python installer\haven_cli.py` | Or use **WSL** and run `./install.sh`. |
| **Run** (already installed) | `./allhaven.sh run` / `./allhaven.sh start` | `run` = foreground (Ctrl+C stops all); `start` = background. |
| **Restart / stop** | `./allhaven.sh restart` / `./allhaven.sh stop` | Restarts/stops backend + frontend + control agent. |

> **Python 3** and **Node.js 18+** are required. If either is missing, the launcher
> stops early and tells you where to get it. On Windows, tick **"Add Python to PATH"**
> when installing Python.

**Everything runs in the terminal.** The launcher checks Python and Node, then installs
and starts Haven with **live progress** — tool checks, `.env` (with backup), the Docker
image pull when Docker is available, `pip`/`npm` installs, migrations, services, and
finally opening the app in your browser. There is no separate website to configure.

> **After setup**, just use `./allhaven.sh run` (or `start`) to launch, and
> `./allhaven.sh restart` / `stop` to manage the servers + control agent. Re-run the
> installer anytime with `HAVEN_FORCE_SETUP=1`. Prefer a browser-based wizard? It's
> optional: `HAVEN_SETUP_WEB=1 ./install.sh`.

---

## 2. The steps (terminal installer, and the optional `HAVEN_SETUP_WEB=1` wizard)

The default terminal installer runs these automatically with live output. The optional
browser wizard (`HAVEN_SETUP_WEB=1`) presents the same steps as clickable screens:

1. **Welcome** — what Haven will do. Docker is recommended for PostgreSQL.
2. **Choose OS** — auto-detected; change it only to see the right Docker guidance.
3. **System Check** — Docker installed/running, Docker Compose, `.env`,
   `docker-compose.yml`, and project folders. Green = good.
4. **Docker Help** — if Docker is missing or not running, follow the guide and
   click **Check Again**. (See *Installing Docker* below.)
5. **Ports** — pick the Frontend / Backend / Postgres ports. The wizard warns
   about ports already in use and can **suggest a free one**.
6. **Apply config** — writes `.env`. Existing secrets are **kept and never shown**;
   a timestamped backup (`.env.bak-…`) is made before any change.
7. **Start services** — starts PostgreSQL (Docker) and the Haven control agent.
8. **Health check** — confirms backend / frontend / database. If something is
   down, it tells you why (and points you back to *Ports* on a conflict).
9. **Finish** — creates a **Haven** desktop shortcut and opens the app.

---

## 3. Installing Docker

Docker runs Haven's database (and is recommended overall).

| OS | Install |
|----|---------|
| **Windows** | Docker Desktop — <https://docs.docker.com/desktop/install/windows-install/> then **open Docker Desktop** so the whale icon is steady. |
| **macOS** | Docker Desktop — <https://docs.docker.com/desktop/install/mac-install/> then open it once. |
| **Linux** | Docker Engine — <https://docs.docker.com/engine/install/> then `sudo systemctl start docker` (and `sudo usermod -aG docker $USER`, then re-login). |

- **Installed but not running?** Open Docker Desktop (Win/Mac) or start the
  service (Linux), wait ~30s, then click **Check Again**.

---

## 4. Opening Haven after installation

- Double-click the **Haven** desktop shortcut, **or** open the launcher file again.
- Because `.env` now exists, it skips the wizard: it installs any missing
  dependencies (**first run only** — this can take a few minutes), waits for the
  database, runs migrations, starts the backend & frontend, and opens
  `http://localhost:<frontend port>` once they're healthy.
- Progress is printed in the launcher window and saved to `var/logs/` (`setup.log`,
  `backend.log`, `frontend.log`).

---

## 5. Start / Stop / Restart services

Inside the app: **Settings → System Control**. Each service (Backend, Frontend,
PostgreSQL, and any optional n8n / Ollama) shows live status, port, and buttons:

- **Start / Stop / Restart** — performed by the local **Haven Agent** (host
  processes) or Docker Compose (database). Non-destructive — **volumes are never
  deleted**.
- **Logs** — last few hundred lines, with secrets masked.

> If you see *"Haven Agent is not running"*, start Haven via the launcher / desktop
> icon. Status and existing state are still shown; controls light up once the agent
> is up.

You can also stop everything from a terminal with `./allhaven.sh stop` (host
processes) or `docker compose stop postgres` (database).

---

## 6. Changing ports later

**Settings → System Control → Ports.** Edit a port, then **Save** (apply on next
restart) or **Save & Restart Services**. The previous `.env` is backed up first;
if the Postgres port changes, the database URL is updated automatically.

---

## 7. Troubleshooting

| Symptom | Fix |
|---------|-----|
| *"Cannot reach the AllHaven API"* on login | The backend isn't up yet. On first run it's still installing dependencies — wait a minute and reload. Otherwise re-open the launcher (it now waits for the backend to be healthy before opening) or check **Settings → System Control** and `var/logs/backend.log`. |
| First launch is slow / seems stuck | Normal on the **first** run: it's creating the Python venv, running `pip install`, and `npm install`. Watch `var/logs/setup.log`. Subsequent launches are fast. |
| `password authentication failed for user "allhaven"` | The Postgres container's credentials don't match `.env`. Easiest: `docker compose up -d postgres` from the repo (uses the matching defaults), or set the role's password to match. |
| Port already in use | Re-run the wizard's **Ports** step (or Settings → System Control → Ports) and pick a free port — use **Suggest**. |
| Docker "not running" | Open Docker Desktop / start the Docker service, wait, then **Check Again**. |
| Wizard won't open | Make sure Python 3 is installed and on PATH, then re-open the launcher. The wizard prints its URL in the console window. |
| macOS blocks the `.command` | Right-click → **Open**, or Privacy & Security → **Open Anyway**. |

---

## How it works (for the curious)

- **Entry points** check Python 3 and Node.js. Fresh install → `./install.sh`
  (Linux/macOS) or `python installer\haven_cli.py` (Windows), which runs the terminal
  installer (`installer/haven_cli.py`); optional web wizard → `installer/haven_setup.py`.
  Once installed, `./allhaven.sh` (`run`/`start`/`restart`/`stop`) manages the services
  (`installer/haven_launch.py` ensures services + opens the app).
- The **Haven Agent** (`installer/haven_agent.py`) is a tiny **localhost-only**,
  **token-gated** control service. It is the *only* place that starts/stops
  processes or runs Docker — always via fixed argument lists (no shell), against a
  strict **allowlist** of services and actions. It never runs destructive commands.
- The app's **Settings → System Control** talks to the agent through the
  authenticated backend; the browser never touches Docker or your shell.
