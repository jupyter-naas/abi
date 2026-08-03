import type { NextConfig } from 'next';

/**
 * `frame-ancestors 'none'` (plus the legacy X-Frame-Options) keeps the admin UI
 * out of an attacker's iframe. The CSP is deliberately conservative but allows
 * `'unsafe-inline'` for scripts: the theme bootstrap in app/layout.tsx is an
 * inline <script>, and Next injects inline bootstrap scripts of its own.
 * Tightening this to a nonce means routing a per-request nonce through both —
 * worth doing, but it is a behavioural change rather than a header tweak.
 */
const isDev = process.env.NODE_ENV !== 'production';

/**
 * `next dev` compiles client chunks with `eval` and talks to the HMR server over
 * a websocket, so the production policy blocks all client JS in dev — React
 * never hydrates and forms fall back to native submits. Relax those two
 * directives for dev only; the deployed policy is unaffected.
 */
const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ''}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${isDev ? ' ws: wss:' : ''}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ');

const SECURITY_HEADERS = [
  { key: 'Content-Security-Policy', value: CSP },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=31536000; includeSubDomains',
  },
];

const nextConfig: NextConfig = {
  output: 'standalone',
  async headers() {
    return [{ source: '/:path*', headers: SECURITY_HEADERS }];
  },
  webpack(config) {
    config.module.rules.push({
      test: /\.ya?ml$/,
      type: 'asset/source',
    });
    return config;
  },
};

export default nextConfig;
