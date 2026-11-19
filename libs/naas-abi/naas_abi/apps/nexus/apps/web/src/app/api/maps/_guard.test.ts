import { afterEach, describe, expect, it, vi } from 'vitest';

import { signedIn, stubPassCheck, upstreamCalls } from '@/lib/testing/web-pass';

import { keptAnswerBytes, mapsRoute, resetMapsGuard } from './_guard';

// Every Maps proxy but `custom/`, which takes the caller's Bearer token.
const ROUTES = [
  'ais',
  'country-centers',
  'firms',
  'flights',
  'gdacs',
  'gulf-strikes',
  'iss',
  'natural-earth',
  'news',
  'nhc',
  'nws',
  'openaq',
  'place',
  'place/photo',
  'streetview',
] as const;

afterEach(() => {
  vi.useRealTimers();
  resetMapsGuard();
  vi.unstubAllGlobals();
  delete process.env.GOOGLE_MAPS_API_KEY;
  delete process.env.FIRMS_MAP_KEY;
  delete process.env.OPENAQ_API_KEY;
});

describe('maps proxies', () => {
  it('keep the deployment keys unspent for anonymous callers', async () => {
    process.env.GOOGLE_MAPS_API_KEY = 'maps-server-key-123456';
    process.env.FIRMS_MAP_KEY = 'abcdef0123456789abcdef0123456789';
    process.env.OPENAQ_API_KEY = 'openaq-key';
    const mock = stubPassCheck(async () => Response.json({}));
    for (const name of ROUTES) {
      const { GET } = (await import(`./${name}/route`)) as { GET: (req: Request) => Promise<Response> };
      const url = `http://nexus-web.test/api/maps/${name}?lat=48.85&lng=2.35&ref=abc&REQUEST=GetMap`;
      expect((await GET(new Request(url))).status, name).toBe(401);
      const unknown = new Request(url, { headers: { cookie: 'nexus-web-pass=abi_gk_unknown_x; nexus-auth-flag=true' } });
      expect((await GET(unknown)).status, name).toBe(401);
    }
    expect(upstreamCalls(mock)).toEqual([]);
  });

  it('keep each user within a rate, and an upstream answer reused', async () => {
    stubPassCheck();
    const handler = vi.fn(async () => Response.json({ ok: true }, { headers: { 'Cache-Control': 'public, max-age=60' } }));
    const GET = mapsRoute('test', handler, { perMinute: 3, cacheSeconds: 60 });

    const first = await GET(signedIn('http://nexus-web.test/api/maps/test?b=2&a=1'));
    expect(first.status).toBe(200);
    expect(first.headers.get('cache-control')).toBe('private, max-age=60');
    // The same question, its parameters in another order: answered from the server's copy.
    const second = await GET(signedIn('http://nexus-web.test/api/maps/test?a=1&b=2'));
    expect(await second.json()).toEqual({ ok: true });
    expect(handler).toHaveBeenCalledTimes(1);

    expect((await GET(signedIn('http://nexus-web.test/api/maps/test?a=3'))).status).toBe(200);
    const limited = await GET(signedIn('http://nexus-web.test/api/maps/test?a=4'));
    expect(limited.status).toBe(429);
    expect(limited.headers.get('retry-after')).toBe('60');
    expect(handler).toHaveBeenCalledTimes(2);
  });

  it('keep the server copies within a byte budget, expired ones going first', async () => {
    stubPassCheck();
    resetMapsGuard({ budgetBytes: 1000 });
    vi.useFakeTimers({ toFake: ['Date'] });
    const body = (tag: string) => tag.padEnd(400, '.');
    const short = vi.fn(async (req: Request) => new Response(body(new URL(req.url).search)));
    const long = vi.fn(async (req: Request) => new Response(body(new URL(req.url).search)));
    const brief = mapsRoute('brief', short, { perMinute: 100, cacheSeconds: 1 });
    const lasting = mapsRoute('lasting', long, { perMinute: 100, cacheSeconds: 600 });

    await brief(signedIn('http://nexus-web.test/api/maps/brief?a=1'));
    await lasting(signedIn('http://nexus-web.test/api/maps/lasting?b=1'));
    expect(keptAnswerBytes()).toBe(800);

    vi.setSystemTime(Date.now() + 2_000);
    await lasting(signedIn('http://nexus-web.test/api/maps/lasting?b=2'));
    // The expired copy made room; the live one is still served from the server.
    expect(keptAnswerBytes()).toBe(800);
    await lasting(signedIn('http://nexus-web.test/api/maps/lasting?b=1'));
    expect(long).toHaveBeenCalledTimes(2);

    for (let i = 3; i < 10; i++) await lasting(signedIn(`http://nexus-web.test/api/maps/lasting?b=${i}`));
    expect(keptAnswerBytes()).toBeLessThanOrEqual(1000);
  });
});
