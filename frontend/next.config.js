/** @type {import('next').NextConfig} */
// Mobile build target (Capacitor): emit a static export in `out/` that the
// Android WebView serves locally. Toggle with `BUILD_TARGET=mobile`.
const isMobile = process.env.BUILD_TARGET === "mobile";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Voice input uses the browser speech recognizer, which needs microphone
  // access on this same origin. Keep location/camera disabled.
  { key: "Permissions-Policy", value: "geolocation=(), microphone=(self), camera=()" },
];

// The production CSP is request-scoped in middleware.ts so every Next.js
// bootstrap/streaming script receives a fresh nonce. A static headers() policy
// cannot safely permit those inline scripts without `unsafe-inline`.

const nextConfig = isMobile
  ? {
      reactStrictMode: true,
      // Static HTML/JS bundle for Capacitor (no Node server in the app). The static
      // site lands in `out/` (Capacitor's webDir). NOTE: `build:mobile` deletes the
      // throwaway `.next` afterward so an APK build never leaves an export build in
      // `.next` that the web dev server would then serve with no CSS.
      output: "export",
      // Required by `output: export` (no Image Optimization server). The app
      // uses no next/image today; this keeps export safe if that changes.
      images: { unoptimized: true },
      // Emit each route as a folder with index.html so file-based serving in
      // the WebView resolves routes without a server rewriter.
      trailingSlash: true,
      // Keep the static build-id directory stable for native APK bundling.
      // Flutter assets are declared ahead of time in pubspec.yaml.
      generateBuildId: async () => "allhaven-mobile",
      // No headers(): a static export cannot emit HTTP headers. Security posture
      // for the app is governed by the native shell (capacitor.config.ts) and
      // the API itself; see docs/MOBILE.md.
    }
  : {
      reactStrictMode: true,
      // Lean production image: emit a self-contained server in .next/standalone.
      output: "standalone",
      async headers() {
        return [{ source: "/:path*", headers: securityHeaders }];
      },
    };

module.exports = nextConfig;
