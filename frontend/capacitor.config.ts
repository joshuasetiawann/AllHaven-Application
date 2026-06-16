import type { CapacitorConfig } from "@capacitor/cli";

// Capacitor wraps the static Next.js export (frontend/out) in a native Android
// shell. The app authenticates with a bearer token (see lib/mobileAuth.ts) and
// talks to the AllHaven backend over the network. The target API URL has a
// build-time default (NEXT_PUBLIC_API_BASE_URL) but is also configurable at
// runtime in Settings → Backend Bridge (lib/backendUrl.ts) — the only way to
// reach the desktop from the phone, where localhost is the device itself.
// Cleartext http:// to a Tailscale IP is allowed via
// android/app/src/main/res/xml/network_security_config.xml. See docs/MOBILE.md.
const config: CapacitorConfig = {
  appId: "id.allhaven.app",
  appName: "AllHaven",
  webDir: "out",
  server: {
    // Serve the bundled app over https://localhost inside the WebView.
    androidScheme: "https",
  },
};

export default config;
