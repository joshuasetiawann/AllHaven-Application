# Architecture

AllHaven is a local-first, modular web application: a **FastAPI** backend, a **PostgreSQL**
database, and a **Next.js (App Router)** frontend.

## Topology (MVP)

```
┌────────────────────┐        HTTPS/JSON         ┌────────────────────┐
│  Next.js frontend  │  ───────────────────────► │   FastAPI backend  │
│  localhost:3000    │  ◄─────────────────────── │   localhost:8000   │
└────────────────────┘    standard envelopes      └─────────┬──────────┘
                                                            │ SQLAlchemy
                                                            ▼
                                                  ┌────────────────────┐
                                                  │    PostgreSQL      │
                                                  │   localhost:5432   │
                                                  └────────────────────┘

Optional (documented, not enabled by default): Ollama (11434), n8n (5678),
Supabase, Google Calendar, Weather API.
```

## Backend layers

The backend keeps responsibilities strictly separated so logic stays testable and routers
stay thin.

| Layer       | Location              | Responsibility |
|-------------|-----------------------|----------------|
| **api**     | `app/api/routers`     | HTTP routing, request/response mapping only |
| **schemas** | `app/schemas`         | Pydantic validation & API contracts |
| **services**| `app/services`        | Business logic, audit logging, integration adapters |
| **domain**  | `app/domain`          | SQLAlchemy models (data access) |
| **core**    | `app/core`            | Settings, database, security, responses, exceptions |

Request flow:

```
Router (thin)  →  Service (business logic + audit)  →  Domain model  →  DB
   ▲ Pydantic schema in/out                 ▲ Principal (user_id, workspace_id)
```

### The Principal

Authenticated requests resolve to an immutable `Principal` (`app/core/principal.py`) holding
`user_id` and `workspace_id`. Services accept the `Principal` rather than raw client input, so
**the client can never supply its own `workspace_id`** and every query is workspace-scoped.

### Standard response envelopes

```jsonc
// success
{ "status": "success", "data": { }, "message": "..." }
// error
{ "status": "error", "error_code": "NOT_FOUND", "message": "...", "details": { } }
```

Centralized handlers (`app/core/exceptions.py`) guarantee this shape and never leak stack traces.

## Database

- UUID primary keys, `TIMESTAMPTZ` timestamps.
- `workspace_id` on all business data; `created_by` / `updated_by` where relevant.
- `is_deleted` soft-delete flag on user-owned content.
- Append-only `audit_logs` for create/update/delete actions.
- Portable column types (`app/domain/base.py`) map to native PostgreSQL types (UUID, JSONB,
  TEXT[]) and to SQLite for the test suite.

Migrations are managed by Alembic (`backend/alembic`). The initial migration creates the full
schema; `alembic upgrade head` must succeed against a real PostgreSQL database.

## Frontend layers

| Layer        | Location              | Responsibility |
|--------------|-----------------------|----------------|
| **app**      | `app/`                | Routes & layouts (App Router) |
| **components**| `components/ui`, `components/layout` | Reusable primitives & shell |
| **lib**      | `lib/`                | API client, auth/token storage, formatting |
| **types**    | `types/`              | Shared TypeScript contracts |

The API client (`lib/api.ts`) reads `NEXT_PUBLIC_API_BASE_URL`, attaches the bearer token, and
unwraps the standard envelope into typed data or an `ApiException`.

## Design system

The UI implements the Stitch "AllHaven Command Center" tokens: a matte "Deep Night" palette
(`#0B0E14` background, `#161B22` glass panels, `#30363D` hairline borders), an electric-cyan
primary (`#00F5FF`), a muted-royal secondary (`#8A2BE2`), and Inter/Geist typography.
