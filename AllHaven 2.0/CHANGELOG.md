# Changelog

All notable changes to **AllHaven Command Center** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.
A bigger change means a bigger bump (see [`docs/VERSIONING.md`](docs/VERSIONING.md)).
Full, detailed notes for every release live in [`docs/releases/`](docs/releases/).

## [Unreleased]

- _Nothing yet._

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
