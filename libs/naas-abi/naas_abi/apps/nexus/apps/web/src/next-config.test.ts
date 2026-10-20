import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);

const atLeast = (version: string, min: [number, number, number]) => {
  const parts = version.split('.').map((n) => parseInt(n, 10));
  for (let i = 0; i < 3; i += 1) {
    if ((parts[i] ?? 0) !== min[i]) return (parts[i] ?? 0) > min[i];
  }
  return true;
};

describe('next.config.js security settings', () => {
  it('runs a Next.js release with the AVIF image-optimizer RCE fixed', () => {
    // GHSA-2xp9-vwfh-vxw4: unauthenticated RCE in /_next/image, fixed in 15.5.24.
    const nextVersion: string = require('next/package.json').version;
    expect(atLeast(nextVersion, [15, 5, 24])).toBe(true);
  });

  it('enables the Image Optimization API only for allow-listed remote hosts', () => {
    const config = require('../next.config.js');
    expect(config.images?.unoptimized).not.toBe(true);
    for (const pattern of config.images?.remotePatterns ?? []) {
      expect(pattern.protocol).toBe('https');
      expect(pattern.hostname).not.toBe('**');
    }
  });
});
