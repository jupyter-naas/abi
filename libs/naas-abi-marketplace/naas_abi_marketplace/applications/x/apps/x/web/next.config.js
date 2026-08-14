/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  // Served under Nexus /app-html/x/apps/x/ from object storage.
  basePath: "/app-html/x/apps/x",
  images: { unoptimized: true },
  skipTrailingSlashRedirect: true,
  trailingSlash: true,
};

module.exports = nextConfig;
