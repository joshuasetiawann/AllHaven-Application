/**
 * Pure URL-policy helpers shared by the browser resolver and Node regressions.
 * All comparisons use WHATWG URL parsing so network-path references and
 * backslashes are interpreted exactly as fetch() would interpret them.
 */

/** @param {{protocol: string, hostname: string}} page */
function pageOrigin(page) {
  const protocol = String(page?.protocol || "").toLowerCase();
  let hostname = String(page?.hostname || "");
  if (hostname.includes(":") && !hostname.startsWith("[")) hostname = `[${hostname}]`;
  if (protocol !== "http:" && protocol !== "https:") throw new TypeError("Unsupported page protocol");
  return new URL(`${protocol}//${hostname}/`);
}

/**
 * Whether an HttpOnly SameSite cookie can safely back a frontend -> API URL.
 *
 * Cookie mode requires the exact page scheme + hostname; ports may differ.
 * Relative paths are resolved against the page origin before comparison. This
 * matters for values such as `//host` and `\\host`: URL() without a base rejects
 * them, while browsers resolve them as cross-host network-path references.
 *
 * @param {string} targetUrl
 * @param {{protocol: string, hostname: string}} page
 */
function cookieBackendMatchesPage(targetUrl, page) {
  if (!targetUrl) return false;
  try {
    const origin = pageOrigin(page);
    const target = new URL(targetUrl, origin);
    return target.protocol === origin.protocol && target.hostname === origin.hostname;
  } catch {
    return false;
  }
}

/** @param {string} hostname */
function isLoopbackHostname(hostname) {
  let host = String(hostname || "").trim().toLowerCase();
  if (host.startsWith("[") && host.endsWith("]")) host = host.slice(1, -1);
  host = host.replace(/\.$/, "");

  if (host === "localhost" || host.endsWith(".localhost") || host === "localhost.localdomain") return true;
  if (host === "0.0.0.0" || host === "::" || host === "::1") return true;

  const ipv4 = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (ipv4 && Number(ipv4[1]) === 127 && ipv4.slice(1).every((part) => Number(part) <= 255)) return true;

  // URL.hostname canonicalises ::ffff:127.0.0.1 to ::ffff:7f00:1.
  const mapped = host.match(/^::ffff:([0-9a-f]{1,4}):([0-9a-f]{1,4})$/i);
  if (mapped) {
    const high = Number.parseInt(mapped[1], 16);
    return Number.isFinite(high) && (high >> 8) === 127;
  }
  return false;
}

/**
 * Whether cleartext HTTP is confined to an address carried by the user's
 * private LAN/tailnet. Public backends must use HTTPS before bearer credentials
 * are attached. IPv6 literals deliberately return false: unlike RFC1918 and
 * Tailscale's documented IPv4 CGNAT range, an arbitrary IPv6 address cannot be
 * classified as private from spelling alone without a broader routing policy.
 *
 * @param {string} hostname
 */
function isPrivateBridgeHostname(hostname) {
  let host = String(hostname || "").trim().toLowerCase();
  if (host.startsWith("[") && host.endsWith("]")) host = host.slice(1, -1);
  host = host.replace(/\.$/, "");
  if (!host) return false;

  // Tailscale MagicDNS/Serve names are controlled within the user's tailnet.
  if (/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+ts\.net$/.test(host)) {
    return true;
  }

  const match = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!match) return false;
  const octets = match.slice(1).map(Number);
  if (octets.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
    return false;
  }
  const [a, b] = octets;
  return (
    a === 10
    || (a === 172 && b >= 16 && b <= 31)
    || (a === 192 && b === 168)
    || (a === 100 && b >= 64 && b <= 127)
  );
}

/**
 * Rewrite an explicit absolute loopback backend to the page's loopback spelling.
 * This preserves the configured backend port/path while keeping cookies and the
 * JS-readable CSRF cookie on one hostname. Network-path and backslash inputs are
 * deliberately ineligible for rewriting.
 *
 * @param {string} targetUrl
 * @param {{protocol: string, hostname: string}} page
 * @returns {string}
 */
function rewriteLoopbackBackendForPage(targetUrl, page) {
  const raw = String(targetUrl || "").trim();
  if (!/^https?:\/\//i.test(raw) || raw.includes("\\")) return "";
  try {
    const origin = pageOrigin(page);
    const target = new URL(raw);
    if (target.protocol !== origin.protocol || target.username || target.password) return "";
    if (!isLoopbackHostname(target.hostname) || !isLoopbackHostname(origin.hostname)) return "";
    target.hostname = origin.hostname;
    return target.href;
  } catch {
    return "";
  }
}

module.exports = {
  cookieBackendMatchesPage,
  isPrivateBridgeHostname,
  isLoopbackHostname,
  rewriteLoopbackBackendForPage,
};
