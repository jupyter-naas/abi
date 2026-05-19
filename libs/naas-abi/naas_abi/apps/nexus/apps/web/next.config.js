const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Prevent socket.io-client / ws from being bundled into server chunks.
  // ws is a Node.js-native WebSocket library; when Next.js tries to create a
  // vendor chunk for it (vendor-chunks/ws@x.y.z.js) the file may be absent in
  // the production container, causing "Cannot find module" at runtime.
  serverExternalPackages: ['ws', 'bufferutil', 'utf-8-validate'],
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
