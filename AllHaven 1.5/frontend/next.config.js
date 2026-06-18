/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Lean production image: emit a self-contained server in .next/standalone.
  output: "standalone",
};

module.exports = nextConfig;
