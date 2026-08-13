# AllHaven setup

Everything needed to install and run AllHaven, split by operating system.
Run the entry point at the repository root; the files here are what it calls.

| | Linux / macOS | Windows |
|---|---|---|
| **First install** | `./install.sh` | `AllHaven-Setup.exe`, or `install.bat` |
| **Everyday control** | `./allhaven.sh` | `AllHaven.bat` |

## `windows/`

| File | What it is |
|---|---|
| `allhaven_windows.py` | The setup wizard **and** the control panel. Stdlib only, so it freezes cleanly into an `.exe`. |
| `Install-AllHaven.bat` | Runs the setup wizard using an installed Python. |
| `AllHaven.bat` | Opens the control panel (start / stop / status / logs / database mode). |
| `build_exe.py` | Freezes `allhaven_windows.py` into `AllHaven-Setup.exe` with PyInstaller. |
| `AllHaven.iss` | Inno Setup script that wraps the whole thing into a signed-style Windows installer with a Start Menu entry and an uninstaller. |
| `dev-start.bat`, `dev-stop.bat` | **Developer** helpers that run the backend and frontend natively (Python + Node). Not part of a normal install. |

The Windows path runs the entire stack in Docker, so a person installing AllHaven
needs neither Python nor Node — only Docker Desktop, which the wizard installs
for them through winget after asking.

## `linux-macos/`

| File | What it is |
|---|---|
| `start.sh`, `stop.sh` | Start and stop the app (thin wrappers over `./allhaven.sh`). |
| `doctor.sh` | Diagnose a broken setup. |
| `healthcheck.sh` | Probe the running services. |

The first-install script (`install.sh`) and the day-to-day launcher
(`allhaven.sh`) stay at the repository root, matching `install.bat` and
`AllHaven.bat` on the Windows side.

## Choosing ports

The wizard asks which host ports to publish on, flags anything already listening,
and offers the next free port. They are stored as `FRONTEND_PORT` and
`BACKEND_PORT` in `.env.prod`, and the control panel can change them later.

Only the host side moves — inside Docker the containers keep 3000 and 8000, so
nothing else needs reconfiguring. Changing the **backend** port rebuilds the
frontend image, because the API address is compiled into the web app.

## Choosing where data is stored

Setup asks one question that shapes the whole deployment:

| Mode | Where data lives | Auto sync | Works offline |
|---|---|---|---|
| **Both** (recommended) | Local PostgreSQL container | Mirrors to Supabase every 15s | Yes |
| **Local only** | Local PostgreSQL container | Off — nothing to mirror | Yes |
| **Supabase only** | Your Supabase project | Off — it would copy the database onto itself | No |

The mode is derived from `DATABASE_URL` rather than stored separately, so the two
can never disagree. `GET /api/v1/health` reports `primary_db` and the effective
`sync_interval_seconds`.

### No Supabase project yet?

Setup asks whether you already have one. If you do, paste the URL and keys from
Dashboard → Settings → API. If you don't, it creates the project for you: give it
a [personal access token](https://supabase.com/dashboard/account/tokens), pick an
organisation and a region, and it provisions the project, waits for it to come up,
and reads the API keys back automatically. The token is used once and never stored.

In **Both** mode the wizard also runs AllHaven's migrations against Supabase — with
row-level security enabled — so a brand-new project has the tables the mirror needs.
Without that step every sync pass would fail against an empty project.
