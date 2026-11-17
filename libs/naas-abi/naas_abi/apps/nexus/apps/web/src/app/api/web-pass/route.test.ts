import { afterEach, describe, expect, it, vi } from 'vitest';

import { LIVE_PASS, stubPassCheck } from '@/lib/testing/web-pass';

import { DELETE, GET, POST } from './route';

afterEach(() => {
  vi.unstubAllGlobals();
});

const keep = (pass: string, headers: Record<string, string> = {}) =>
  POST(
    new Request('https://nexus.example.com/api/web-pass', {
      method: 'POST',
      headers: { 'content-type': 'application/json', host: 'nexus.example.com', ...headers },
      body: JSON.stringify({ web_pass: pass }),
    }),
  );

const held = () =>
  GET(new Request('https://nexus.example.com/api/web-pass', { headers: { cookie: `nexus-web-pass=${LIVE_PASS}` } }));

describe('web pass route', () => {
  it('keeps only a live pass, set by this app, in an httpOnly strict cookie', async () => {
    stubPassCheck();

    const elsewhere = await keep(LIVE_PASS, { origin: 'https://other.example', 'sec-fetch-site': 'cross-site' });
    expect(elsewhere.status).toBe(403);
    expect(elsewhere.headers.getSetCookie()).toEqual([]);
    const otherOrigin = await keep(LIVE_PASS, { origin: 'https://other.example' });
    expect(otherOrigin.status).toBe(403);

    const refused = await keep('abi_gk_unknown_pass', { origin: 'https://nexus.example.com' });
    expect(refused.status).toBe(401);
    expect(refused.headers.getSetCookie()).toEqual([]);

    const kept = await keep(LIVE_PASS, { origin: 'https://nexus.example.com', 'sec-fetch-site': 'same-origin' });
    expect(kept.status).toBe(200);
    const [pass, until] = kept.headers.getSetCookie();
    expect(pass).toContain(`nexus-web-pass=${LIVE_PASS}`);
    expect(pass).toContain('HttpOnly');
    expect(pass).toContain('SameSite=Strict');
    expect(pass).toContain('Secure');
    expect(pass).toContain('Max-Age=3600');
    // Its readable twin says when it ends, and holds nothing of the pass.
    expect(until).toMatch(/^nexus-web-pass-until=\d+; /);
    expect(until).not.toContain('HttpOnly');
    expect(until).not.toContain(LIVE_PASS);
  });

  it('keeps working behind a proxy that rewrites Host', async () => {
    stubPassCheck();
    const kept = await keep(LIVE_PASS, {
      host: 'nexus-web:3000',
      origin: 'https://nexus.example.com',
      'sec-fetch-site': 'same-origin',
    });
    expect(kept.status).toBe(200);
  });

  it('answers whether a pass is held from the API each time, and drops it', async () => {
    const mock = stubPassCheck();
    expect(await (await held()).json()).toEqual({ active: true, expires_in: 3600 });
    expect(await (await held()).json()).toEqual({ active: true, expires_in: 3600 });
    // No kept answer: a pass revoked elsewhere reads as gone at the next check.
    expect(mock).toHaveBeenCalledTimes(2);
    const none = await GET(new Request('https://nexus.example.com/api/web-pass'));
    expect(await none.json()).toEqual({ active: false });

    const dropped = await DELETE(
      new Request('https://nexus.example.com/api/web-pass', {
        method: 'DELETE',
        headers: { host: 'nexus.example.com', origin: 'https://nexus.example.com' },
      }),
    );
    const cookies = dropped.headers.getSetCookie();
    expect(cookies).toHaveLength(2);
    for (const cookie of cookies) expect(cookie).toContain('Max-Age=0');
  });
});
