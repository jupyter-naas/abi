/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  // A placeholder: the module serves the app at /app-remote/<grant>/... with a
  // per-session grant, and its ASGI app (x_proxy/app.py) replaces this string
  // with the request's root_path in what it serves. Keep it equal to APP_BASE
  // in src/lib/base.ts and APP_ROOT_PLACEHOLDER in app.py.
  basePath: "/__x_proxy_app_root__",
  images: { unoptimized: true },
  skipTrailingSlashRedirect: true,
  trailingSlash: true,
};

module.exports = nextConfig;
