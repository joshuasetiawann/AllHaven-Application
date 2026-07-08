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
  android: {
    // The bundled app is served as https://localhost, while a private desktop
    // bridge may be plain HTTP on LAN/Tailscale (192.168.x.x / 100.x.y.z).
    // Allow mixed content so Backend Bridge tests and REST calls can reach it.
    allowMixedContent: true,
  },
  server: {
    // Serve the bundled app over https://localhost inside the WebView.
    androidScheme: "https",
    // Permit cleartext requests from the WebView to private LAN/Tailscale
    // bridge URLs. The app never embeds service-role secrets in the client.
    cleartext: true,
  },
  plugins: {
    // On Android, route HTTP through Capacitor's native stack. This avoids
    // WebView-only failures where Chrome can open the LAN/Tailscale backend but
    // fetch() inside the APK is blocked by mixed-content/CORS quirks.
    CapacitorHttp: {
      enabled: true,
    },
  },
};

export default config;
