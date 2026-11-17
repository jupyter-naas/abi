/** Web pass helpers for route tests: a signed-in request, and the API's answer to its check. */
import { vi } from 'vitest';

import { WEB_PASS_COOKIE } from '@/lib/web-pass';
import { forgetWebPasses } from '@/lib/web-pass-server';

export const LIVE_PASS = 'abi_gk_testpass_livesecret';
export const PASS_HOLDER = 'usr_ada';

/** A request that carries the live pass, as a signed-in browser's would. */
export function signedIn(url: string, init: RequestInit = {}): Request {
  const headers = new Headers(init.headers);
  headers.set('cookie', `${WEB_PASS_COOKIE}=${LIVE_PASS}`);
  return new Request(url, { ...init, headers });
}

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

/**
 * Stub `fetch`: the API's pass check (`/api/auth/oidc/web-pass`) knows `LIVE_PASS`
 * only; every other request goes to `others` (by default: a failure). Returns the mock.
 */
export function stubPassCheck(others?: FetchLike) {
  forgetWebPasses();
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url;
    if (url.endsWith('/api/auth/oidc/web-pass')) {
      const presented = new Headers(init?.headers).get('X-Web-Pass');
      return presented === LIVE_PASS
        ? Response.json({ user_id: PASS_HOLDER, expires_in: 3600 })
        : Response.json({ detail: 'Not signed in' }, { status: 401 });
    }
    if (others) return others(input, init);
    throw new Error(`unexpected fetch ${url}`);
  });
  vi.stubGlobal('fetch', mock);
  return mock;
}

/** The calls `mock` made to anything but the pass check. */
export function upstreamCalls(mock: ReturnType<typeof stubPassCheck>): string[] {
  return mock.mock.calls
    .map(([input]) => (typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url))
    .filter((url) => !url.endsWith('/api/auth/oidc/web-pass'));
}
