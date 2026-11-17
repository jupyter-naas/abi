import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { PublicFetchResult } from '@/lib/public-fetch';
import { signedIn, stubPassCheck } from '@/lib/testing/web-pass';

// A remote answer to serve instead of the network, when a test sets one.
const remote = vi.hoisted(() => ({ next: null as PublicFetchResult | null }));
vi.mock('@/lib/public-fetch', async (importOriginal) => {
  const real = await importOriginal<typeof import('@/lib/public-fetch')>();
  return {
    ...real,
    fetchPublic: (url: string, options: Parameters<typeof real.fetchPublic>[1]) =>
      remote.next ? Promise.resolve(remote.next) : real.fetchPublic(url, options),
  };
});

import { GET } from './route';

/** A service on 127.0.0.1, standing for one inside the deployment's network. */
let internal: http.Server;
let base = '';
const reached: string[] = [];

beforeAll(async () => {
  internal = http.createServer((req, res) => {
    reached.push(req.url ?? '');
    if (req.url?.startsWith('/redirect')) {
      res.writeHead(302, { Location: `${base}/internal` }).end();
      return;
    }
    res.writeHead(200, { 'Content-Type': 'text/html' }).end('<script>secret</script>');
  });
  await new Promise<void>((resolve) => internal.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${(internal.address() as AddressInfo).port}`;
});

afterAll(() => new Promise<void>((resolve) => internal.close(() => resolve())));

afterEach(() => {
  remote.next = null;
  reached.length = 0;
  vi.unstubAllGlobals();
});

const imageData = (url: string, raw = false) =>
  `http://nexus-web.test/api/image-data?${raw ? 'raw=1&' : ''}url=${encodeURIComponent(url)}`;

describe('image-data', () => {
  it('keeps anonymous callers from fetching anything', async () => {
    stubPassCheck();
    for (const target of [`${base}/internal`, `${base}/redirect`, 'https://example.com/a.png']) {
      for (const raw of [false, true]) {
        const res = await GET(new Request(imageData(target, raw)));
        expect(res.status).toBe(401);
        const unknown = await GET(
          new Request(imageData(target, raw), { headers: { cookie: 'nexus-web-pass=abi_gk_unknown_x' } }),
        );
        expect(unknown.status).toBe(401);
      }
    }
    expect(reached).toEqual([]);
  });

  it('keeps signed-in callers off internal addresses, directly and through redirects', async () => {
    stubPassCheck();
    for (const target of [
      `${base}/internal`,
      `${base}/redirect`,
      `https://127.0.0.1:${new URL(base).port}/internal`,
      'https://127.0.0.1/internal',
      'https://169.254.169.254/latest/meta-data/',
      'https://[::1]/internal',
      'file:///etc/passwd',
    ]) {
      const res = await GET(signedIn(imageData(target)));
      expect(res.status, target).toBeGreaterThanOrEqual(400);
      const body = (await res.json()) as { dataUri?: string };
      expect(body.dataUri).toBeUndefined();
    }
    expect(reached).toEqual([]);
  });

  it('keeps raw answers to inert raster images', async () => {
    stubPassCheck();
    for (const contentType of ['text/html', 'image/svg+xml', 'application/xml', 'text/javascript', '']) {
      remote.next = { status: 200, contentType, body: Buffer.from('<script>x</script>'), url: 'https://example.com/x' };
      const res = await GET(signedIn(imageData('https://example.com/x', true)));
      expect(res.status, contentType).toBe(415);
      expect(res.headers.get('content-type')).toContain('application/json');
    }

    remote.next = { status: 200, contentType: 'image/png; charset=binary', body: Buffer.from('png'), url: 'https://example.com/x.png' };
    const res = await GET(signedIn(imageData('https://example.com/x.png', true)));
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toBe('image/png');
    expect(res.headers.get('x-content-type-options')).toBe('nosniff');
    expect(res.headers.get('content-security-policy')).toContain('sandbox');
    expect(res.headers.get('content-security-policy')).toContain("default-src 'none'");
    expect(res.headers.get('cache-control')).toContain('private');

    remote.next = { status: 200, contentType: 'image/webp', body: Buffer.from('webp'), url: 'https://example.com/x.webp' };
    const json = await GET(signedIn(imageData('https://example.com/x.webp')));
    expect(await json.json()).toEqual({ dataUri: `data:image/webp;base64,${Buffer.from('webp').toString('base64')}` });
  });
});
