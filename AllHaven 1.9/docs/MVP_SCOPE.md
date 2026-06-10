# MVP Scope

A deliberately small MVP on a scalable foundation. The workspace model exists from day one to
avoid painful future migration, but team features are out of scope.

## In scope (built)

**Backend**
- FastAPI app, centralized settings, standard response envelopes, exception handling
- PostgreSQL + SQLAlchemy models + Alembic initial migration
- Local auth boundary: register, login, current user (password hashing, JWT)
- Default workspace creation + owner membership on register
- Tasks CRUD (workspace-scoped, soft delete, audited)
- Notes CRUD (tags, pinning, optional q/tag filters, soft delete, audited)
- Finance: categories CRUD, transactions CRUD, monthly summary (soft delete, audited)
- Audit log service for create/update/delete
- AI chat foundation: sessions, messages, honest not-configured replies
- AI tool proposal model + list + reject (no execution)
- Integration status endpoint (honest, secret-free)
- Test suite (health, models, auth, tasks, notes, finance, AI, settings)

**Frontend**
- Login/register page wired to auth
- Dashboard shell (sidebar + topbar), overview with integration status
- Tasks, Notes, Finance, AI Chat, Settings pages wired to the API
- Reusable UI components; loading / empty / error states
- Premium dark "command center" design system

## Out of scope (intentionally not built)

- Real OS / kernel / system services; mobile app
- Google Drive clone / full file storage
- n8n clone / visual workflow builder; WordPress-like app builder
- Real Google Calendar / Supabase Auth / Weather API / Ollama execution
- Team invitations, billing, advanced RBAC, workspace switching
- Two-way calendar sync, full RAG knowledge base
- Financial advice or money movement
- **AI auto-execution of write actions** (proposals are listed and can be rejected only)

## One default workspace per user

Register creates exactly one workspace with the user as `owner`. No sharing, no invitations, no
role management in the MVP — but `workspace_id` is present on every business row so multi-member
workspaces can be added later without a data migration.
