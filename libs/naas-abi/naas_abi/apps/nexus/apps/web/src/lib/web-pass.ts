/**
 * The web pass, browser side: what lets this app's own server routes
 * (`/api/image-data`, `/api/maps/*`) know the browser is signed in.
 *
 * The API's session cookie never reaches this host. Once the session is known,
 * the browser asks the API for a pass (`POST /api/auth/oidc/web-pass`, with the
 * session and its CSRF token) and hands it to `POST /api/web-pass`, which keeps
 * it in an httpOnly cookie of this host: page script never holds it after that.
 * Next to it, the readable cookie `WEB_PASS_UNTIL_COOKIE` says when it ends: a
 * hint for this page only (the routes check the pass itself).
 *
 * Pages that call those routes wait for `webPassReady()` (the workspace layout
 * does, `useWebPassReady`), so their first requests carry the pass. A pass lasts
 * as long as the session at most, eight hours at most; it is renewed while the
 * app is open and dropped when the session ends. Server side: `web-pass-server.ts`.
 */

export const WEB_PASS_COOKIE = 'nexus-web-pass';
export const WEB_PASS_UNTIL_COOKIE = 'nexus-web-pass-until';
export const WEB_PASS_ROUTE = '/api/web-pass';

/** Renew a pass that has less than this left. */
const RENEW_BEFORE_SECONDS = 30 * 60;
/** A pass with less than this left is not counted on by a page that starts now. */
const READY_MARGIN_SECONDS = 60;
const CHECK_EVERY_MS = 10 * 60 * 1000;
const READY_TIMEOUT_MS = 5_000;

let pending: Promise<boolean> | null = null;
let timer: ReturnType<typeof setInterval> | null = null;
let settleNext: ((held: boolean) => void) | null = null;
let nextResult: Promise<boolean> | null = null;

/** Seconds left on this host's pass, as its readable twin says (0 without one). */
export function webPassSecondsLeft(now: number = Date.now()): number {
  if (typeof document === 'undefined') return 0;
  for (const part of document.cookie.split(';')) {
    const [name, value] = part.trim().split('=');
    if (name !== WEB_PASS_UNTIL_COOKIE) continue;
    const until = Number(value);
    return Number.isFinite(until) ? Math.max(0, Math.floor(until - now / 1000)) : 0;
  }
  return 0;
}

async function heldSecondsLeft(): Promise<number> {
  const res = await fetch(WEB_PASS_ROUTE, { cache: 'no-store', credentials: 'same-origin' });
  if (!res.ok) return 0;
  const body = (await res.json()) as { active?: unknown; expires_in?: unknown };
  return body.active === true && typeof body.expires_in === 'number' ? body.expires_in : 0;
}

/** Make sure this host holds a live pass for the session; true when it does. */
export function ensureWebPass(apiBase: string, csrfToken: () => string | null): Promise<boolean> {
  if (typeof window === 'undefined') return Promise.resolve(false);
  pending ??= (async () => {
    let held = false;
    try {
      if ((await heldSecondsLeft()) > RENEW_BEFORE_SECONDS) {
        held = true;
        return held;
      }
      const token = csrfToken();
      const made = await fetch(`${apiBase.replace(/\/$/, '')}/api/auth/oidc/web-pass`, {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        headers: token ? { 'X-CSRF-Token': token } : {},
      });
      if (!made.ok) return held;
      const { web_pass: webPass } = (await made.json()) as { web_pass?: unknown };
      if (typeof webPass !== 'string' || !webPass) return held;
      const kept = await fetch(WEB_PASS_ROUTE, {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ web_pass: webPass }),
      });
      held = kept.ok;
      return held;
    } catch {
      return held;
    } finally {
      pending = null;
      const settle = settleNext;
      settleNext = null;
      nextResult = null;
      settle?.(held);
    }
  })();
  return pending;
}

/**
 * Resolves once this host holds a live pass (true), or when it cannot get one
 * soon (false): at once when the pass in hand has time left, else when the
 * running (or next) `ensureWebPass` ends, `timeoutMs` at most.
 */
export function webPassReady(timeoutMs: number = READY_TIMEOUT_MS): Promise<boolean> {
  if (typeof window === 'undefined') return Promise.resolve(false);
  if (webPassSecondsLeft() > READY_MARGIN_SECONDS) return Promise.resolve(true);
  const next =
    pending ??
    (nextResult ??= new Promise<boolean>((resolve) => {
      settleNext = resolve;
    }));
  return Promise.race([
    next,
    new Promise<boolean>((resolve) => setTimeout(() => resolve(false), timeoutMs)),
  ]);
}

/** Keep a pass while the app is open: now, then every ten minutes. */
export function keepWebPass(apiBase: string, csrfToken: () => string | null): void {
  if (typeof window === 'undefined') return;
  void ensureWebPass(apiBase, csrfToken);
  timer ??= setInterval(() => void ensureWebPass(apiBase, csrfToken), CHECK_EVERY_MS);
}

/** Drop this host's pass (the session ended): no renewal, and the cookie goes. */
export function dropWebPass(): void {
  if (typeof window === 'undefined') return;
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  void fetch(WEB_PASS_ROUTE, { method: 'DELETE', credentials: 'same-origin' }).catch(() => undefined);
}
