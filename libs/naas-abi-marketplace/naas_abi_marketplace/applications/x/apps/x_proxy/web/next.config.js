/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  // Served under Nexus /app-html/x/apps/x_proxy/ from object storage.
  basePath: "/app-html/x/apps/x_proxy",
  images: { unoptimized: true },
  skipTrailingSlashRedirect: true,
  trailingSlash: true,
};

module.exports = nextConfig;
