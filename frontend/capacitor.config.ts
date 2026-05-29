import type { CapacitorConfig } from "@capacitor/cli";

// Capacitor wraps the static Next.js export (frontend/out) in a native Android
// shell. The app authenticates with a bearer token (see lib/mobileAuth.ts) and
// talks to the AllHaven backend over the network — set the target API URL at
// build time via NEXT_PUBLIC_API_BASE_URL. See docs/MOBILE.md.
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
