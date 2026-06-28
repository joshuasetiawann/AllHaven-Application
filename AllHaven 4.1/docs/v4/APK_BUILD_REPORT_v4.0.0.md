# APK Build Report — AllHaven v4.0.0

**Result: ✅ SUCCESS** — built with the project's **existing** Capacitor tooling (no new
native stack added).

## How it was built
- Tooling: the existing **GitHub Actions** workflow `.github/workflows/android-apk.yml`
  (Capacitor 8 + `npm run build:mobile` static export → `cap sync android` → `gradlew
  assembleDebug`). No Android SDK was installed locally; the build runs on GitHub runners.
- Trigger: `gh workflow run android-apk.yml --ref main -f api_base_url="https://joo.tail01a7d3.ts.net/api/v1"`
- Source commit: `786b94e` (main, v4.0.0).
- Run: `27856945294` — **conclusion: success**.

## Artifact
- **`app-debug.apk`** (~4.82 MB) published to the **`mobile-latest`** GitHub pre-release.
- It is a **debug** APK (not store-signed), so Android shows an "install unknown apps"
  prompt — expected.
- The app shows **v4.0.0** (login + sidebar + Settings) and connects to Supabase directly
  for data; backend/bridge features use the configured API base URL.

## Install
- On the phone: open the repo → **Releases → "AllHaven Mobile (latest debug build)"** →
  download `app-debug.apk` → allow "install unknown apps" → install.
- Or: `gh release download mobile-latest -p app-debug.apk`.

## Notes / honesty
- The artifact filename from CI is the generic `app-debug.apk` (the CI publishes to the
  `mobile-latest` rolling pre-release). A versioned copy can be saved as
  `AllHaven-v4.0.0-android.apk` when downloading (`gh release download mobile-latest -p
  app-debug.apk -O release/v4.0.0/AllHaven-v4.0.0-android.apk`).
- **Before mobile register works end-to-end**, Supabase migration **0016** must be applied
  (see `SUPABASE_MIGRATION_GUIDE_v4.0.0.md`). The APK itself is built and installable
  regardless; this is a server-side prerequisite for the register flow.
- No new dependency, Android SDK, or `sudo` was needed (existing CI tooling only).
