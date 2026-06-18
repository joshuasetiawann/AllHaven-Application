# Haven — Desktop Setup (beginner guide)

This guide is for non-technical users. You only need to **clone the repo** and
**open one file**. The setup wizard does the rest.

---

## 1. Open the launcher for your OS

| Your OS | Double-click | Notes |
|---------|--------------|-------|
| **Windows** | `START_HAVEN_WINDOWS.bat` | If Windows SmartScreen warns, click *More info → Run anyway*. |
| **macOS** | `START_HAVEN_MAC.command` | First time: **right-click → Open** (or System Settings → Privacy & Security → *Open Anyway*). |
| **Linux** | `START_HAVEN_LINUX.sh` | If double-click doesn't run it, open a terminal and run `./START_HAVEN_LINUX.sh`. |

> Only **Python 3** is required to run the wizard. If it's missing, the launcher
> tells you where to get it (<https://www.python.org/downloads/>) — on Windows be
> sure to tick **"Add Python to PATH"**.

The wizard opens at `http://127.0.0.1:7000` in your browser.

---

## 2. The wizard, step by step

1. **Welcome** — what Haven will do. Docker is required.
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
- Because `.env` now exists, it skips the wizard: it makes sure the control agent
  and services are running, then opens `http://localhost:<frontend port>`.

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
| *"Cannot reach the AllHaven API"* on login | Backend or database isn't up. Open **Settings → System Control** (or re-run the launcher). Check the database is running and the backend health is green. |
| `password authentication failed for user "allhaven"` | The Postgres container's credentials don't match `.env`. Easiest: `docker compose up -d postgres` from the repo (uses the matching defaults), or set the role's password to match. |
| Port already in use | Re-run the wizard's **Ports** step (or Settings → System Control → Ports) and pick a free port — use **Suggest**. |
| Docker "not running" | Open Docker Desktop / start the Docker service, wait, then **Check Again**. |
| Wizard won't open | Make sure Python 3 is installed and on PATH, then re-open the launcher. The wizard prints its URL in the console window. |
| macOS blocks the `.command` | Right-click → **Open**, or Privacy & Security → **Open Anyway**. |

---

## How it works (for the curious)

- **Launchers** (`START_HAVEN_*`) only need Python 3. First run → setup wizard
  (`installer/haven_setup.py`); later runs → `installer/haven_launch.py` (ensure
  services + open).
- The **Haven Agent** (`installer/haven_agent.py`) is a tiny **localhost-only**,
  **token-gated** control service. It is the *only* place that starts/stops
  processes or runs Docker — always via fixed argument lists (no shell), against a
  strict **allowlist** of services and actions. It never runs destructive commands.
- The app's **Settings → System Control** talks to the agent through the
  authenticated backend; the browser never touches Docker or your shell.
