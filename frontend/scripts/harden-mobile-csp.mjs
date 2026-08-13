import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const outputRoot = join(process.cwd(), "out");
const BASE_POLICY = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "img-src 'self' data: blob:",
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self'",
  "script-src-attr 'none'",
  "font-src 'self' data:",
  "connect-src 'self' http: https:",
];

function htmlFiles(directory) {
  const files = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) files.push(...htmlFiles(path));
    else if (entry.endsWith(".html")) files.push(path);
  }
  return files;
}

function inlineScriptHashes(html) {
  const hashes = new Set();
  const scripts = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  for (const match of html.matchAll(scripts)) {
    if (/\bsrc\s*=/i.test(match[1])) continue;
    const digest = createHash("sha256").update(match[2], "utf8").digest("base64");
    hashes.add(`'sha256-${digest}'`);
  }
  return [...hashes].sort();
}

if (!existsSync(outputRoot)) throw new Error("Mobile export directory 'out' is missing.");

const files = htmlFiles(outputRoot);
if (files.length === 0) throw new Error("Mobile export contains no HTML files.");

let totalInlineScripts = 0;
for (const file of files) {
  const html = readFileSync(file, "utf8");
  if (/http-equiv=["']Content-Security-Policy["']/i.test(html)) {
    throw new Error(`${relative(outputRoot, file)} already contains a CSP meta tag.`);
  }
  const hashes = inlineScriptHashes(html);
  totalInlineScripts += hashes.length;
  const policy = [...BASE_POLICY.slice(0, 5), `${BASE_POLICY[5]} ${hashes.join(" ")}`, ...BASE_POLICY.slice(6)].join("; ");
  const encodedPolicy = policy.replaceAll("&", "&amp;").replaceAll('"', "&quot;");
  const meta = `<meta http-equiv="Content-Security-Policy" content="${encodedPolicy}">`;
  const hardened = html.replace(/<head>/i, (head) => `${head}${meta}`);
  if (hardened === html || hardened.includes("script-src 'self' 'unsafe-inline'")) {
    throw new Error(`${relative(outputRoot, file)} has an unsafe or incomplete script policy.`);
  }
  const metaPosition = hardened.search(/http-equiv="Content-Security-Policy"/i);
  const firstScriptPosition = hardened.search(/<script\b/i);
  if (metaPosition < 0 || (firstScriptPosition >= 0 && metaPosition > firstScriptPosition)) {
    throw new Error(`${relative(outputRoot, file)} does not place CSP before executable content.`);
  }
  for (const hash of hashes) {
    if (!policy.includes(hash)) {
      throw new Error(`${relative(outputRoot, file)} is missing an inline script hash.`);
    }
  }
  if (/fonts\.(?:googleapis|gstatic)\.com/i.test(hardened)) {
    throw new Error(`${relative(outputRoot, file)} still depends on a CSP-blocked remote font.`);
  }
  writeFileSync(file, hardened, "utf8");
}

console.log(`Hardened ${files.length} mobile HTML files with ${totalInlineScripts} route-specific script hashes.`);
