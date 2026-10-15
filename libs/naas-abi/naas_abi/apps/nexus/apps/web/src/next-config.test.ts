import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);

describe('next.config.js security settings', () => {
  it('keeps the Image Optimization API off until Next.js >= 15.5.24', () => {
    // GHSA-2xp9-vwfh-vxw4: unauthenticated RCE in /_next/image when AVIF files are processed.
    const config = require('../next.config.js');
    const nextVersion: string = require('next/package.json').version;
    const [major, minor, patch] = nextVersion.split('.').map(Number);
    const patched = major > 15 || (major === 15 && (minor > 5 || (minor === 5 && patch >= 24)));
    if (!patched) expect(config.images?.unoptimized).toBe(true);
  });
});
