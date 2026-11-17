import http from 'node:http';
import type { AddressInfo } from 'node:net';
import { NextRequest } from 'next/server';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { LIVE_PASS, stubPassCheck } from '@/lib/testing/web-pass';

import { GET } from './route';

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
    res
      .writeHead(200, { 'Content-Type': 'text/html' })
      .end('<meta property="og:title" content="INTERNAL">');
  });
  await new Promise<void>((resolve) => internal.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${(internal.address() as AddressInfo).port}`;
});

afterAll(() => new Promise<void>((resolve) => internal.close(() => resolve())));

afterEach(() => {
  reached.length = 0;
  vi.unstubAllGlobals();
});

const preview = (url: string, cookie?: string) =>
  new NextRequest(`http://nexus-web.test/api/link-preview?url=${encodeURIComponent(url)}`, {
    headers: cookie ? { cookie } : {},
  });

describe('link-preview', () => {
  it('keeps internal pages unread, for anonymous and signed-in callers', async () => {
    stubPassCheck();
    for (const target of [`${base}/redirect`, `${base}/internal`]) {
      expect((await GET(preview(target))).status).toBe(401);
      const signedIn = await GET(preview(target, `nexus-web-pass=${LIVE_PASS}`));
      expect((await signedIn.json()).title).toBeUndefined();
    }
    const https = await GET(preview(`https://127.0.0.1:${new URL(base).port}/internal`, `nexus-web-pass=${LIVE_PASS}`));
    expect((await https.json()).title).toBeUndefined();
    expect(reached).toEqual([]);
  });
});
