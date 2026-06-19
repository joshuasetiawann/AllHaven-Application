/** @type {import('next').NextConfig} */
const isProd = process.env.NODE_ENV === "production";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "geolocation=(), microphone=(), camera=()" },
];

// CSP only in production: dev needs 'unsafe-eval' for Fast Refresh/HMR, which we
// don't want to allow in the shipped app. Styles use 'unsafe-inline' (Tailwind/
// Next inject <style>); connect-src allows the local API and any HTTPS API host.
if (isProd) {
  securityHeaders.push({
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "img-src 'self' data: blob:",
      "style-src 'self' 'unsafe-inline'",
      "script-src 'self' 'unsafe-inline'",
      "font-src 'self' data:",
      "connect-src 'self' http://localhost:8000 https:",
    ].join("; "),
  });
}

const nextConfig = {
  reactStrictMode: true,
  // Lean production image: emit a self-contained server in .next/standalone.
  output: "standalone",
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

module.exports = nextConfig;
