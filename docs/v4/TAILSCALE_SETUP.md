# Desktop Bridge / Tailscale Setup — AllHaven v4.0

Ollama and n8n are **desktop-local** services. The Desktop Bridge lets mobile reach
them over Tailscale. **API-key AI providers and Supabase data do NOT need the bridge.**

## Connection modes (per service: Ollama, n8n)
| Mode | URL field | When |
|------|-----------|------|
| `local_desktop` | `base_url` (e.g. `http://localhost:11434`) | On the desktop machine itself |
| `tailscale_private` | `tailscale_url` (e.g. `http://100.x.y.z:11434`) | From mobile, inside your tailnet (recommended) |
| `tailscale_serve` | `serve_url` (`https://host.tailnet.ts.net/…`) | Private Serve URL inside the tailnet |
| `tailscale_funnel` | `funnel_url` | **PUBLIC internet — off by default**, demo only |
| `auto` | — | Tries Local → Private → Serve (never Funnel) |

The resolver (`backend/app/services/connection_resolver.py`) picks the URL for the
selected mode; status is **honest** — online only if the resolved endpoint actually
responds (`/api/tags` for Ollama, a safe health/base GET for n8n).

## Setup from mobile (Private mode — recommended)
1. Install Tailscale on the desktop and the phone; sign both into the **same tailnet**.
2. Get the desktop's Tailscale IP (`100.x.y.z`) or MagicDNS host (`tailscale status`).
3. In **Settings → Connected Tools → Ollama / n8n**: set **Connection mode = Tailscale
   Private** and paste the Tailscale URL (port `11434` for Ollama, `5678` for n8n).
4. **Test Connection.** Online only if it responds.

## Funnel (public) — disabled by default
- `funnel_enabled` defaults to `false`. The resolver returns **no URL** for Funnel mode
  unless `funnel_enabled = true` is explicitly set (a checkbox with a red warning in the UI).
- Never expose raw Ollama/n8n via Funnel. If used, route only through the authenticated
  AllHaven app. Intended only for temporary Public Demo mode.

## Deployment profiles (`DEPLOYMENT_PROFILE`)
- `private` (default) — owner/internal; mobile uses the Desktop Bridge.
- `client_portal` — hosted/multi-tenant; clients are **not** prompted to connect a desktop bridge.
- `public_demo` — temporary public preview; Funnel optional + off by default.

`GET /api/v1/health` returns `app_version` + `deployment_profile`.

## Gating rules (honest, no fakes)
- Ollama / n8n: **unavailable** if none of the configured endpoints respond.
- API-key AI providers (OpenAI, Claude, Gemini, Grok, DeepSeek, Qwen, OpenRouter, …):
  **independent of Tailscale** — gated only by a valid key + provider reachability. Saving
  a key marks *Configured*; *Online* requires a successful Test Connection.

## Verify
```
cd backend && pytest tests/test_desktop_bridge.py     # 10 passed
# resolver + honest gating + funnel-off-by-default + API-provider independence
```

## Web app over Tailscale (same-origin) — the desktop browser UI

To open the **full web app** (not just the API) from any device's browser over the
tailnet, serve the frontend (`:3000`) and backend (`:8000`) under **one HTTPS origin**.
Same-origin is required: the desktop build authenticates with a `SameSite=Lax`
HttpOnly session cookie, which the browser only sends to a same-site backend. Serving
the API on a *different* origin makes `/auth/me` 401 → login bounces back to `/login`.

```sh
tailscale serve reset
# Backend under /api. NOTE: --set-path STRIPS the matched prefix, so the target
# MUST end in /api for the stripped remainder to re-append (→ /api/v1/... reaches it).
tailscale serve --bg --set-path /api http://127.0.0.1:8000/api
# Frontend at the root (Next handles /login, /dashboard, /_next/* …).
tailscale serve --bg --set-path /   http://127.0.0.1:3000
tailscale serve status
```
Result — one origin, mobile APK unaffected (its `/api/v1/*` calls route straight to
the backend, no extra hop):
- `https://<host>.ts.net/`            → frontend
- `https://<host>.ts.net/api/v1/...`  → backend

The frontend resolves its API base **same-origin** automatically when served this way
(`frontend/lib/backendUrl.ts`); leave `NEXT_PUBLIC_API_BASE_URL` unset for the dev
server. A cross-site Backend Bridge override is ignored in cookie mode so a stale URL
can't cause the login loop. `--bg` persists across reboots.
