import type { NextConfig } from 'next';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8001';

const nextConfig: NextConfig = {
  turbopack: {},
  serverExternalPackages: ['cesium'],
  // Proxy /api/* to the WSR FastAPI backend so the browser never hits CORS.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_BASE}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
