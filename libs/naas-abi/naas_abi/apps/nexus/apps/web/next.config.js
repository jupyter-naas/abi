const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Keep make check / production builds from overwriting a running dev server.
  // distDir must stay relative to this app (Next does not accept absolute paths).
  distDir: process.env.NODE_ENV === 'development' ? '.next-dev' : '.next',
  transpilePackages: ['@nexus/ui', '@embedpdf/snippet', 'three'],
  // next dev only: keep compiled pages for an hour (default 60s), so going back
  // from Organization/Platform Settings to a workspace does not recompile it.
  onDemandEntries: {
    maxInactiveAge: 60 * 60 * 1000,
    pagesBufferLength: 25,
  },
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
  webpack(config) {
    // pnpm's strict package isolation stops webpack from resolving this ESM-only
    // package through normal module lookup; point it directly to the bundle file.
    config.resolve.alias['@embedpdf/snippet'] = path.resolve(
      __dirname,
      'node_modules/@embedpdf/snippet/dist/embedpdf.js'
    );
    return config;
  },
  async redirects() {
    return [
      // Workspace Settings → Theme was renamed Settings → General.
      {
        source: '/workspace/:workspaceId/settings/theme',
        destination: '/workspace/:workspaceId/settings/general',
        permanent: true,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: '/login',
        destination: '/auth/login',
      },
      {
        source: '/register',
        destination: '/auth/register',
      },
      // /app-html/* is handled by the route handler (or Caddy → ABI). Do not
      // rewrite here and never forge ABI_API_KEY for anonymous browsers.
    ];
  },
  images: {
    // Security: no Image Optimization API (/_next/image). Next < 15.5.24 has an
    // unauthenticated RCE there when AVIF files are processed (GHSA-2xp9-vwfh-vxw4),
    // and every <Image> in the app already passes `unoptimized`, so nothing uses it.
    // Remove once Next.js is upgraded to >= 15.5.24.
    unoptimized: true,
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'upload.wikimedia.org',
      },
      {
        protocol: 'https',
        hostname: 'duckduckgo.com',
      },
      {
        protocol: 'https',
        hostname: '*.wikipedia.org',
      },
    ],
  },
};

module.exports = nextConfig;
