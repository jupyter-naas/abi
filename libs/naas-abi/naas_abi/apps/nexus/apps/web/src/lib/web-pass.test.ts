// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type WebPass = typeof import('./web-pass');

let webPass: WebPass;

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

function urlOf(input: RequestInfo | URL): string {
  return typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
}

beforeEach(async () => {
  vi.resetModules();
  webPass = await import('./web-pass');
  document.cookie = `${webPass.WEB_PASS_UNTIL_COOKIE}=; max-age=0; path=/`;
});

afterEach(() => {
  // Ends the renewal timer a test started.
  vi.stubGlobal('fetch', vi.fn(async () => Response.json({ active: false })));
  webPass.dropWebPass();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('web pass readiness', () => {
  it('keeps pages waiting until the pass is kept, then lets them go', async () => {
    const kept = deferred<Response>();
    const calls: string[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = urlOf(input);
        calls.push(`${init?.method ?? 'GET'} ${url}`);
        if (url === '/api/web-pass' && (init?.method ?? 'GET') === 'GET') return Response.json({ active: false });
        if (url.endsWith('/api/auth/oidc/web-pass')) return Response.json({ web_pass: 'abi_gk_a_b', expires_in: 3600 });
        if (url === '/api/web-pass' && init?.method === 'POST') return kept.promise;
        return Response.json({});
      }),
    );

    // A page mounts before the session is known: it waits.
    let settled: boolean | undefined;
    void webPass.webPassReady(60_000).then((held) => {
      settled = held;
    });
    webPass.keepWebPass('https://api.test', () => 'csrf');
    await vi.waitFor(() => expect(calls).toHaveLength(3));
    expect(settled).toBeUndefined();

    kept.resolve(Response.json({ active: true, expires_in: 3600 }));
    await vi.waitFor(() => expect(settled).toBe(true));
    expect(calls).toEqual([
      'GET /api/web-pass',
      'POST https://api.test/api/auth/oidc/web-pass',
      'POST /api/web-pass',
    ]);
  });

  it('keeps no page waiting while the pass in hand has time left', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    document.cookie = `${webPass.WEB_PASS_UNTIL_COOKIE}=${Math.floor(Date.now() / 1000) + 3600}; path=/`;
    expect(webPass.webPassSecondsLeft()).toBeGreaterThan(3500);
    await expect(webPass.webPassReady()).resolves.toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('keeps pages from waiting longer than the timeout', async () => {
    vi.useFakeTimers();
    const ready = webPass.webPassReady(5_000);
    await vi.advanceTimersByTimeAsync(5_000);
    await expect(ready).resolves.toBe(false);
  });
});
