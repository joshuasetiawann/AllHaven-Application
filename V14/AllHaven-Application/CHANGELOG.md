# Changelog

All notable changes to **AllHaven Command Center** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`.
A bigger change means a bigger bump (see [`docs/VERSIONING.md`](docs/VERSIONING.md)).
Full, detailed notes for every release live in [`docs/releases/`](docs/releases/).

## [Unreleased]

- _Nothing yet._

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
