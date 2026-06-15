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
    const apiBase =
      process.env.NEXUS_INTERNAL_API_URL ||
      process.env.NEXUS_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://localhost:9879';

    return [
      {
        source: '/login',
        destination: '/auth/login',
      },
      {
        source: '/register',
        destination: '/auth/register',
      },
      {
        source: '/app-html/:path*',
        destination: `${apiBase}/app-html/:path*`,
      },
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
