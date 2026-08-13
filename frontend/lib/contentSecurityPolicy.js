/**
 * Build the production browser policy. Kept as a small pure module so the
 * middleware and the Node regression test exercise the exact same policy.
 *
 * @param {{ nonce: string, deploymentProfile?: string }} options
 */
function buildContentSecurityPolicy({ nonce, deploymentProfile = "private" }) {
  if (!/^[A-Za-z0-9+/_-]+={0,2}$/.test(nonce)) {
    throw new Error("Invalid CSP nonce");
  }

  const connectSrc =
    deploymentProfile === "private"
      ? "connect-src 'self' http: https:"
      : "connect-src 'self' http://localhost:8000 https:";

  return [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "img-src 'self' data: blob:",
    "style-src 'self' 'unsafe-inline'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "script-src-attr 'none'",
    "font-src 'self' data:",
    connectSrc,
  ].join("; ");
}

module.exports = { buildContentSecurityPolicy };
