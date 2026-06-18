# Versioning

AllHaven Command Center uses [Semantic Versioning](https://semver.org/): **`MAJOR.MINOR.PATCH`**.

> Rule of thumb (as requested): **a bigger update gets a bigger number.**

| Part | When to bump | Example |
|------|--------------|---------|
| **PATCH** (`0.3.0` → `0.3.1`) | Small fixes, copy/UI tweaks, no new capability | bug fix in a provider adapter |
| **MINOR** (`0.3.0` → `0.4.0`) | A new feature or noticeable capability, backward-compatible | a new module, a new chat mode |
| **MAJOR** (`0.x` → `1.0.0`) | Big or breaking change, or the first "stable" release | rewrite, breaking API change |

While the app is pre-`1.0`, we stay in the `0.x` range: it is still evolving and
minor versions may include larger changes.

## Single source of truth

The current version is stored in **`/VERSION`**. These must always match it:

- `/VERSION`
- `frontend/package.json` → `"version"`
- `backend/pyproject.toml` → `version`
- `frontend/components/layout/nav.ts` → `APP_VERSION` (shown in the sidebar, prefixed with `v`)

## How to cut a new version

1. Decide the bump (PATCH / MINOR / MAJOR) using the table above.
2. Update the four places listed under *Single source of truth*.
3. Add a new section at the top of [`CHANGELOG.md`](../CHANGELOG.md).
4. Add a detailed note file in [`docs/releases/`](releases/) named `vX.Y.Z.md`.
5. Commit: `Release vX.Y.Z — <short title>`.
6. Tag it: `git tag -a vX.Y.Z -m "vX.Y.Z — <short title>" && git push origin vX.Y.Z`.

## Release history

| Version | Date | Title |
|---------|------|-------|
| [v0.1.0](releases/v0.1.0.md) | 2026-06-09 | Initial AllHaven Command Center |
| [v0.2.0](releases/v0.2.0.md) | 2026-06-09 | Multi-agent Debate |
| [v0.3.0](releases/v0.3.0.md) | 2026-06-09 | Reasoning Quality Layer |
