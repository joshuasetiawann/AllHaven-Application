# Weather Removal Report — AllHaven v4.0

**Status:** Weather is removed from v4.0 active product scope. Do not re-add.

Weather was already removed from the UI/nav/AI-tool/provider in v3.8. v4.0 completes
the removal of the **residual active backend + frontend surface** while preserving DB
migration history (removing it would be destructive).

## Audit & classification

| Reference | Type | Action |
|---|---|---|
| `backend/app/api/routers/weather.py` | active (dead — not registered in `main.py`) | **deleted** |
| `backend/app/schemas/weather.py` | active (only imported by the dead router) | **deleted** |
| `backend/app/services/weather_service.py` | active (only used by the dead router) | **deleted** |
| `backend/app/core/config.py` `WEATHER_API_KEY` / `WEATHER_PROVIDER` | active settings | **removed** |
| `.env.example` `WEATHER_API_KEY=` / `WEATHER_PROVIDER=` | active env keys | **removed** |
| `backend/app/services/env_file_service.py` `"weather_api"` allowlist entry | active integration allowlist | **removed** |
| `frontend/lib/apiRest.ts` `weatherApi` + `WeatherLocation`/`WeatherCurrent` imports | active (dead — no caller) | **removed** |
| `frontend/lib/apiSupabase.ts` `weatherApi` + imports | active (dead — no caller) | **removed** |
| `frontend/types/index.ts` `WeatherLocation` / `WeatherCurrent` | active types | **removed** |
| `backend/alembic/versions/0004…/0012…/0013…` `weather_locations` | DB migration history | **kept** (removing is destructive) |
| `weather_locations` table + `backend/app/domain/weather.py` model + sync registry entry | dormant legacy table | **kept, unused & documented** (no UI, no API route, no AI tool) |

## Why the dormant table/model is kept
- Dropping the `weather_locations` table would be a destructive DB migration on local
  Postgres + Supabase (against the spec's `do not run destructive cleanup`).
- The model + sync entry keep the (empty) table internally consistent with the sync
  engine. It is **not reachable by any route, UI, AI tool, or setting**.

## Acceptance (all met)
- ✅ No active Weather sidebar item (removed in v3.8; verified absent).
- ✅ No `/dashboard/weather` page.
- ✅ No Weather API route registered (`grep weather backend/app/main.py` → none).
- ✅ No Weather settings card / integration allowlist entry.
- ✅ No AI tool can call weather (removed in v3.8).
- ✅ App builds with **zero** Weather mentions in the route tree (`next build` → 0).
- ✅ Backend imports clean; **455 tests pass**; frontend `tsc` + `build` clean.

## Verification commands
```
grep -RIn -i weather backend/app/main.py            # → no route registration
cd backend && pytest                                # 455 passed
cd frontend && npx tsc --noEmit && npm run build    # clean, 0 weather in routes
```
