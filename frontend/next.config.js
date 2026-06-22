/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === "production";
// Mobile build target (Capacitor): emit a static export in `out/` that the
// Android WebView serves locally. Toggle with `BUILD_TARGET=mobile`.
const isMobile = process.env.BUILD_TARGET === "mobile";
// Deployment profile shapes how strict the web CSP's connect-src is. In the
// default `private` (local-first / personal) profile the user may point the app
// at their own desktop over Tailscale using a plain-HTTP address
// (http://100.x.y.z:8000), so connect-src must allow `http:`. Hosted profiles
// (client_portal / public_demo) keep it strict: localhost + HTTPS only.
const deploymentProfile = process.env.NEXT_PUBLIC_DEPLOYMENT_PROFILE || "private";
const isPrivateProfile = deploymentProfile === "private";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Voice input uses the browser speech recognizer, which needs microphone
  // access on this same origin. Keep location/camera disabled.
  { key: "Permissions-Policy", value: "geolocation=(), microphone=(self), camera=()" },
];

// CSP only in production: dev needs 'unsafe-eval' for Fast Refresh/HMR, which we
// don't want to allow in the shipped app. Styles use 'unsafe-inline' (Tailwind/
// Next inject <style>). connect-src: HTTPS is always allowed (Tailscale Serve,
// hosted backends); plain http:// is allowed only in the private profile so a
// user-configured Tailscale-IP bridge works without weakening hosted deployments.
if (isProd) {
  const connectSrc = isPrivateProfile
    ? "connect-src 'self' http: https:"
    : "connect-src 'self' http://localhost:8000 https:";
  securityHeaders.push({
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "img-src 'self' data: blob:",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "script-src 'self' 'unsafe-inline'",
      "font-src 'self' data: https://fonts.gstatic.com",
      connectSrc,
    ].join("; "),
  });
}

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
