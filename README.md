<div align="center">

![AllHaven Command Center](docs/assets/banner.svg)

# AllHaven Mobile Branch

**Android APK workspace for AllHaven 4.1.**

This branch is for the mobile build. It keeps the AllHaven UI and feature model, but documents and defaults the project around the Android APK, Supabase mobile data, and the optional desktop Backend Bridge for local services such as Ollama and n8n.

[![Version](https://img.shields.io/badge/mobile-4.1.0-18E0D6?style=flat-square)](CHANGELOG.md)
![Android](https://img.shields.io/badge/Android-APK-3DDC84?style=flat-square&logo=android&logoColor=white)
![Capacitor](https://img.shields.io/badge/Capacitor-8-119EFF?style=flat-square&logo=capacitor&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-mobile%20data-3ECF8E?style=flat-square&logo=supabase&logoColor=white)

[Build APK](#build-apk) | [Mobile Model](#mobile-model) | [Backend Bridge](#backend-bridge) | [Troubleshooting](#troubleshooting)

</div>

---

## Branch Role

| Branch | Purpose |
| --- | --- |
| `main` | Latest desktop/current AllHaven release. |
| `master` | Full archive/recap branch with version folders from the beginning through the latest release. |
| `mobile` | Android APK and mobile-focused workflow branch. |

This branch is not the archive branch and should not be flattened into `master`. It may share most application code with `main`, because the APK is built from the same React/Next.js UI, but its README and workflow are mobile-first.

---

## Mobile Model

The APK has two paths:

| Feature group | Mobile path | Needs desktop bridge? |
| --- | --- | --- |
| Login/register | Supabase Auth | No |
| Tasks, Notes, Finance, Routine, Approvals, Memory | Supabase-backed mobile data layer | No |
| AI provider settings, system controls, Drive/Knowledge backend work | Backend Bridge | Yes |
| Ollama | Desktop over LAN/Tailscale/Serve | Yes |
| n8n | Desktop over LAN/Tailscale/Serve | Yes |

The goal is simple: the APK should keep core workspace features usable without Tailscale, while desktop-local services stay private and are reached only through the bridge.

---

## What Is Included

- Same AllHaven visual layout and UX as the main app.
- Capacitor Android project under `frontend/android`.
- Mobile build script: `frontend/package.json` -> `npm run build:mobile`.
- Supabase client/data layer for mobile mode.
- Native persisted auth token through `@capacitor/preferences`.
- Backend Bridge UI for runtime API URL changes.
- Android network config for local/private bridge URLs.

---

## Build APK

### Requirements

- Node.js 22+ recommended for Capacitor 8.
- JDK 21.
- Android SDK / Android Studio.
- Supabase project URL and anon key.
- Optional desktop backend URL for bridge defaults.

### Debug APK

From the repo root:

```bash
cd frontend

NEXT_PUBLIC_API_BASE_URL=http://<desktop-ip>:8000/api/v1 \
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co \
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key> \
npm run build:mobile

npx cap sync android
cd android
./gradlew assembleDebug
```

APK output:

```text
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

### Current local build notes

The last known local debug APK path used during AllHaven 4.1 work was:

```text
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

Expected debug size is small because this is a Capacitor WebView shell with static web assets, not a bundled local database/server.

---

## Backend Bridge

Inside the APK, `localhost` means the phone, not your desktop. Use one of these:

| Mode | Example |
| --- | --- |
| LAN | `http://192.168.1.7:8000/api/v1` |
| Tailscale private IP | `http://100.x.y.z:8000/api/v1` |
| Tailscale Serve | `https://desktop-name.tailnet-name.ts.net/api/v1` |

Before expecting the APK to connect, test the same URL in Chrome on the phone:

```text
http://<desktop-ip>:8000/api/v1/health
```

If Chrome cannot open it, the APK cannot open it either.

Run the desktop backend for LAN/Tailscale access:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Supabase Requirements

Mobile mode expects:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Supabase Auth enabled.
- Required schema/RLS migrations applied.
- `provision_me` RPC deployed for first-login provisioning.

For desktop bridge features authenticated by Supabase bearer token, the backend also needs:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`

Never expose the service-role key in frontend/mobile environment variables.

---

## Troubleshooting

### Login says "Something went wrong"

Usually the APK was built without Supabase public config. Rebuild with:

```bash
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
npm run build:mobile
```

Then uninstall the old APK or clear app data before installing the new one.

### Test Connection is offline but Chrome works

Check that the saved URL ends at `/api/v1` or lets AllHaven append it. Then clear the old saved backend URL in the app and test again.

### Raw Tailscale IP does not open on Android

Use Tailscale Serve instead:

```text
https://desktop-name.tailnet-name.ts.net/api/v1
```

### Ollama or n8n is offline

That does not mean the APK is broken. Ollama and n8n are desktop-local services. They need the Backend Bridge and their own reachable URLs.

---

## Verification Checklist

- `npm run build:mobile` succeeds.
- `npx cap sync android` succeeds.
- `./gradlew assembleDebug` succeeds.
- The APK contains the expected Supabase project URL.
- The APK does not contain `PLACEHOLDER.invalid`.
- Chrome on the phone can open the backend `/health` URL before bridge-dependent features are tested.
- Core Supabase-backed features work without Tailscale.

---

## Documentation

- [Mobile APK guide](docs/MOBILE.md)
- [Tailscale setup](docs/v4/TAILSCALE_SETUP.md)
- [Release notes 4.1](docs/v4/RELEASE_NOTES_v4.1.0.md)
- [Desktop setup](docs/DESKTOP_SETUP.md)

---

## License

Copyright (c) 2026 Joshua Setiawan. All rights reserved.

AllHaven Command Center, including the Android APK workflow, source code, design, and documentation, is the intellectual property of Joshua Setiawan. See [LICENSE](LICENSE) for terms.
