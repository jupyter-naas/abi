import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Empty turbopack config: signals we're Turbopack-aware (no webpack migration needed)
  turbopack: {},
  // Cesium uses browser globals; exclude it from server-side bundling
  serverExternalPackages: ['cesium'],
};

export default nextConfig;
