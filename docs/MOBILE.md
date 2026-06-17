# AllHaven Mobile (Android APK)

The mobile app is the **existing Next.js frontend** wrapped in a native Android
shell with [Capacitor](https://capacitorjs.com/). There is **no UI rewrite** — the
same React app is exported as a static bundle, packaged into an `.apk`, and it
talks to the AllHaven backend over the network.

Design spec: [`docs/superpowers/specs/2026-06-17-mobile-apk-design.md`](superpowers/specs/2026-06-17-mobile-apk-design.md).

---

## How it works

```
[ APK on the phone ]
   └─ Android WebView (Capacitor) → static Next.js bundle (frontend/out)
        └─ fetch() → https://<api-host>/api/v1   (FastAPI backend)
```

- **Static export.** `BUILD_TARGET=mobile` switches `next.config.js` to
  `output: "export"`, producing `frontend/out/` (plain HTML/JS, no Node server).
- **Auth = bearer token.** The WebView's origin (`https://localhost`) differs from
  the API host, so cross-origin cookies are unreliable. The mobile build instead
  uses the bearer token the backend already issues on login. This is enabled by
  `NEXT_PUBLIC_AUTH_MODE=bearer`, which the `build:mobile` script **sets for you**.
  The token is stored natively via `@capacitor/preferences`
  (see `frontend/lib/mobileAuth.ts`). **No backend code change is required.**
- **API URL is baked at build time** from `NEXT_PUBLIC_API_BASE_URL`. A shell value
  overrides `frontend/.env.local`, so you point each build at the backend you want
  without editing files. (This is the only env var you need to supply yourself.)

---

## Prerequisites (to produce the `.apk`)

This repo can build the static web bundle anywhere Node runs, but assembling the
actual `.apk` needs the Android toolchain on **your** machine:

- **Node 18+** and npm (already used for the frontend).
- **JDK 17** (Temurin/OpenJDK 17).
- **Android Studio** (includes the Android SDK, platform-tools, and Gradle). On
  first launch it installs the SDK; accept the SDK licenses.

> The dev container these files were built in has no Android SDK, so the `.apk`
> is assembled on your machine. Everything else (Capacitor config, the Android
> project, the bearer-auth code, the verified static export) is already done.

> **Fresh clone:** the committed `android/` project deliberately gitignores the
> Capacitor-generated glue (`capacitor-cordova-android-plugins/`) and web assets,
> because `cap sync` regenerates them. So after cloning, run **`npm run cap:sync`
> once** before opening the project in Android Studio — otherwise Gradle fails
> with `Project with path ':capacitor-cordova-android-plugins' could not be found`.
> The `npm run cap:open` script below does this sync for you.

---

## Phase 1 — build and install on your own phone (LAN)

The backend isn't on the cloud yet, so the phone talks to the dev backend running
on your PC over Wi-Fi. **Phone and PC must be on the same Wi-Fi network.**

1. **Start the backend** on your PC (it listens on `:8000`). In local mode the API
   already accepts requests from any LAN origin (`BACKEND_CORS_ALLOW_ALL` is auto-on).

2. **Find your PC's LAN IP** (e.g. `192.168.1.20`):
   ```bash
   ip addr | grep "inet 192"     # Linux
   # or: ipconfig (Windows) / ipconfig getifaddr en0 (macOS)
   ```

3. **Build + sync + open Android Studio** in one command (from `frontend/`),
   pointing at that IP:
   ```bash
   NEXT_PUBLIC_API_BASE_URL=http://<PC-IP>:8000/api/v1 npm run cap:open
   ```
   `cap:open` runs the mobile build (which sets `NEXT_PUBLIC_AUTH_MODE=bearer`),
   syncs the web assets into the Android project, then opens Android Studio. You
   only supply the API URL. *(Tip: instead of prepending the var every time, set
   `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local`.)*

4. **Build the debug APK** in Android Studio: **Run ▶** on your device, or
   **Build → Build Bundle(s) / APK(s) → Build APK(s)**. CLI alternative:
   ```bash
   cd android && ./gradlew assembleDebug        # gradlew.bat on Windows
   ```
   Output: `frontend/android/app/build/outputs/apk/debug/app-debug.apk`.

5. **Install on the phone:** transfer the `.apk` (USB/Drive/Telegram), enable
   *Install unknown apps* for that source, tap to install. Or over USB:
   ```bash
   adb install app-debug.apk
   ```

6. **Use it:** open AllHaven, register/log in. The token is stored on the device,
   so you stay logged in across app restarts (until it expires — see Limitations).

> **HTTP on the LAN:** phase 1 uses plain `http://` to your PC. That's fine for
> local testing on your own network; do not use it over the public internet.
> Android 9+ allows cleartext to private IPs by default for debug builds.

---

## Phase 2 — publish (cloud backend)

When you deploy the backend to a domain (see `docker-compose.prod.yml` + Caddy):

1. Rebuild + sync pointed at the public API:
   ```bash
   NEXT_PUBLIC_API_BASE_URL=https://<your-domain>/api/v1 npm run cap:sync
   ```
2. **CORS:** production is *not* in local mode, so it only allows the origins in
   `BACKEND_CORS_ORIGINS`. The WebView's origin is `https://localhost`, so add it:
   set `BACKEND_CORS_ORIGINS=https://<your-domain>,https://localhost` on the
   server. (Alternative: enable the native HTTP layer with `CapacitorHttp` to
   bypass browser CORS entirely — a future enhancement.)
3. **Release-sign** the APK instead of debug-signing:
   - Create a keystore once:
     ```bash
     keytool -genkey -v -keystore allhaven.keystore \
       -alias allhaven -keyalg RSA -keysize 2048 -validity 10000
     ```
   - Configure signing in `android/app/build.gradle` (or via Android Studio →
     *Build → Generate Signed Bundle / APK*) and build `assembleRelease`.
   - Keep the keystore + passwords safe; you need the **same** keystore for every
     future update (and for Play Store).

---

## App identity

- **App ID:** `id.allhaven.app` — change in `frontend/capacitor.config.ts`
  **before** any public release (it's the permanent package name on Play Store).
- **App name:** `AllHaven`.
- **Icon / splash:** add your assets and run
  `npx @capacitor/assets generate --android` (install `@capacitor/assets` first),
  or set them manually in `android/app/src/main/res/`.

---

## What changed in the codebase

| File | Change |
|------|--------|
| `frontend/next.config.js` | Conditional `output: "export"` when `BUILD_TARGET=mobile` (desktop still `standalone`). |
| `frontend/capacitor.config.ts` | Capacitor config (appId, appName, `webDir: out`). |
| `frontend/lib/mobileAuth.ts` | Bearer-token store (native `@capacitor/preferences`), mobile-only. |
| `frontend/lib/api.ts` | Shared `authFetchInit()` helper: bearer `Authorization` + `credentials:"omit"` in mobile mode, CSRF + cookie on web. Applied to `request()` **and** the multipart upload helpers (`driveApi.upload`, `knowledgeApi.uploadDocument`); `driveApi.downloadUrl` replaced by an auth-aware `driveApi.download()`. |
| `frontend/components/layout/AppShell.tsx` | Hydrates the token before the first API call. |
| `frontend/app/dashboard/drive/page.tsx` | Uses `driveApi.download()` so file downloads carry auth on mobile. |
| `frontend/package.json` | Capacitor deps + `build:mobile` (bakes `NEXT_PUBLIC_AUTH_MODE=bearer`) / `cap:sync` / `cap:open` (syncs first) scripts. |
| `frontend/android/` | Generated native Android project (committed; build artifacts + regenerated glue gitignored). |

The desktop build is unchanged: with no `BUILD_TARGET`/`NEXT_PUBLIC_AUTH_MODE`,
the bearer paths are inert and the app uses the cookie+CSRF flow exactly as before.

---

## Limitations (v1)

- **Token lifetime 24h, no auto-refresh** → you log in again about once a day.
- **Google OAuth** (redirect-based) is not wired for the in-app WebView yet.
- **No push notifications / biometric unlock** yet.
- **Android only** (no iOS project).
