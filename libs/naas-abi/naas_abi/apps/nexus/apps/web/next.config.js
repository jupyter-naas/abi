const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@nexus/ui', '@embedpdf/snippet'],
  webpack(config) {
    // pnpm's strict package isolation stops webpack from resolving this ESM-only
    // package through normal module lookup; point it directly to the bundle file.
    config.resolve.alias['@embedpdf/snippet'] = path.resolve(
      __dirname,
      'node_modules/@embedpdf/snippet/dist/embedpdf.js'
    );
    return config;
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
