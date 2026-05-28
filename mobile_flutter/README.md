# AllHaven Mobile Flutter Shell

This folder builds the AllHaven mobile APK with Flutter/Dart while preserving the
exact AllHaven UI/UX from the web command center.

The Flutter layer is intentionally thin:

- starts a local Dart asset server inside the APK;
- serves the exported AllHaven Next.js bundle from `assets/allhaven`;
- displays it in a fullscreen Android WebView;
- allows cleartext LAN/Tailscale URLs for private backend, Ollama, and n8n access.

Most app data runs directly through Supabase in the bundled frontend. The backend
bridge remains for features that genuinely need the desktop backend, Ollama, or
n8n.

## Build

From this folder:

```sh
export PATH=/mnt/storage/toolchains/flutter-3.35.7/bin:$PATH
export JAVA_HOME=/mnt/storage/toolchains/jdk-21
export ANDROID_HOME=/mnt/storage/toolchains/android-sdk
export ANDROID_SDK_ROOT=/mnt/storage/toolchains/android-sdk
export PUB_CACHE=/mnt/storage/toolchains/flutter-pub-cache-335

flutter --no-version-check pub get
flutter --no-version-check analyze
flutter --no-version-check test
flutter --no-version-check build apk --debug
```

APK output:

```text
build/app/outputs/flutter-apk/app-debug.apk
```

## Refresh Bundled UI

Rebuild the frontend mobile export, then copy `frontend/out` into
`mobile_flutter/assets/allhaven` before building the APK.

The current bundled export is AllHaven v4.1.0 with Supabase data mode and bearer
auth enabled for mobile.
