import 'server-only';

/**
 * Minimal fixed-window rate limiter for the sign-in route.
 *
 * Scope and limits — read before relying on this:
 * state lives in the module scope, so it is per-process (per Worker isolate).
 * It reliably stops a naive single-source password-guessing loop, but it is not
 * a global counter: a distributed attacker, or traffic spread across isolates,
 * will get proportionally more attempts. Treat it as a floor, and put a
 * Cloudflare Rate Limiting rule in front of `/api/auth/password` for the real
 * ceiling. Anything stronger in-app needs shared state (KV or a Durable Object).
 */

type Window = { count: number; resetAt: number };

const windows = new Map<string, Window>();

/** Bound the map so a rotating-IP flood cannot grow it without limit. */
const MAX_TRACKED_KEYS = 10_000;

function sweep(now: number): void {
  for (const [key, window] of windows) {
    if (window.resetAt <= now) {
      windows.delete(key);
    }
  }
}

export type RateLimitOptions = {
  limit: number;
  windowMs: number;
};

export type RateLimitResult = {
  allowed: boolean;
  /** Seconds until the window resets — send as `Retry-After`. */
  retryAfterSeconds: number;
};

export function checkRateLimit(
  key: string,
  { limit, windowMs }: RateLimitOptions,
): RateLimitResult {
  const now = Date.now();
  const existing = windows.get(key);

  if (!existing || existing.resetAt <= now) {
    if (windows.size >= MAX_TRACKED_KEYS) {
      sweep(now);
    }
    windows.set(key, { count: 1, resetAt: now + windowMs });
    return { allowed: true, retryAfterSeconds: 0 };
  }

  existing.count += 1;
  if (existing.count > limit) {
    return {
      allowed: false,
      retryAfterSeconds: Math.max(1, Math.ceil((existing.resetAt - now) / 1000)),
    };
  }
  return { allowed: true, retryAfterSeconds: 0 };
}

/** Clear the counter for a key — call after a successful sign-in. */
export function resetRateLimit(key: string): void {
  windows.delete(key);
}

/**
 * Best-effort client identity. `CF-Connecting-IP` is set by Cloudflare and is
 * the trustworthy one in production; the others are fallbacks for local runs
 * and are spoofable, which is another reason to enforce at the edge too.
 */
export function clientKeyFromRequest(request: Request): string {
  const headers = request.headers;
  const ip =
    headers.get('cf-connecting-ip') ??
    headers.get('x-real-ip') ??
    headers.get('x-forwarded-for')?.split(',')[0]?.trim() ??
    'unknown';
  return ip;
}
