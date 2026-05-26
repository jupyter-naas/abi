const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Keep socket.io (and its optional Node `ws` dep) out of the SSR bundle.
  serverExternalPackages: ['socket.io-client', 'engine.io-client'],
  transpilePackages: ['@nexus/ui', '@embedpdf/snippet'],
  webpack(config, { isServer }) {
    if (isServer) {
      config.externals = [...(config.externals || []), 'ws'];
    }
    // pnpm's strict package isolation stops webpack from resolving this ESM-only
    // package through normal module lookup; point it directly to the bundle file.
    config.resolve.alias['@embedpdf/snippet'] = path.resolve(
      __dirname,
      'node_modules/@embedpdf/snippet/dist/embedpdf.js'
    );
    // Monaco ships .ttf assets; Next needs an explicit rule.
    config.module.rules.push({
      test: /\.ttf$/,
      type: 'asset/resource',
    });
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
