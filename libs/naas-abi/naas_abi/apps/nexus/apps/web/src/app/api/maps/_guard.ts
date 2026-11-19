import { NextResponse } from 'next/server';

import { requireSignedIn } from '@/lib/web-pass-server';

/**
 * What every Maps proxy keeps (`/api/maps/*`, but `custom/`, which takes the
 * caller's Bearer token):
 *
 * - it answers signed-in users only (their web pass, `lib/web-pass-server.ts`);
 * - each user makes at most `perMinute` requests a minute to one proxy;
 * - a proxy that spends a deployment key (Google, FIRMS, OpenAQ) keeps its
 *   upstream answers on the server for `cacheSeconds`, so repeated requests
 *   reach the upstream once;
 * - answers are `private`: no shared cache keeps what a signed-in user asked.
 */

export type MapsRouteOptions = {
  perMinute: number;
  cacheSeconds?: number;
};

type Handler = (req: Request) => Response | Promise<Response>;

const WINDOW_MS = 60_000;
const MAX_COUNTERS = 20_000;
const MAX_KEPT_ANSWERS = 500;
const MAX_KEPT_BYTES = 2 * 1024 * 1024;
/** All kept answers together, per process. */
const DEFAULT_KEPT_BUDGET_BYTES = 64 * 1024 * 1024;
let keptBudgetBytes = DEFAULT_KEPT_BUDGET_BYTES;
let keptBytes = 0;

const counters = new Map<string, { start: number; count: number }>();

type KeptAnswer = { until: number; status: number; headers: [string, string][]; body: ArrayBuffer };
const answers = new Map<string, KeptAnswer>();

/** Forget every count and kept answer; `budgetBytes` sets the kept answers' budget (tests). */
export function resetMapsGuard({ budgetBytes = DEFAULT_KEPT_BUDGET_BYTES }: { budgetBytes?: number } = {}): void {
  counters.clear();
  answers.clear();
  keptBytes = 0;
  keptBudgetBytes = budgetBytes;
}

/** The bytes the kept answers hold now (tests). */
export function keptAnswerBytes(): number {
  return keptBytes;
}

function allowed(key: string, perMinute: number): boolean {
  const now = Date.now();
  const current = counters.get(key);
  if (!current || now - current.start >= WINDOW_MS) {
    if (counters.size >= MAX_COUNTERS) {
      for (const [name, counter] of counters) {
        if (now - counter.start >= WINDOW_MS) counters.delete(name);
      }
      if (counters.size >= MAX_COUNTERS) return false;
    }
    counters.set(key, { start: now, count: 1 });
    return true;
  }
  current.count += 1;
  return current.count <= perMinute;
}

function answerKey(name: string, req: Request): string {
  const params = new URL(req.url).searchParams;
  params.sort();
  return `${name}?${params.toString()}`;
}

function privateHeaders(headers: Headers): Headers {
  const out = new Headers(headers);
  const cacheControl = out.get('Cache-Control');
  if (!cacheControl || /\bpublic\b/i.test(cacheControl)) {
    out.set('Cache-Control', (cacheControl ?? 'no-store').replace(/\bpublic\b/i, 'private'));
  }
  return out;
}

function forgetAnswer(key: string): void {
  const kept = answers.get(key);
  if (!kept) return;
  keptBytes -= kept.body.byteLength;
  answers.delete(key);
}

/**
 * Keep an answer within the count and byte budgets: expired answers go first,
 * then the oldest live ones.
 */
function keepAnswer(key: string, answer: KeptAnswer): void {
  const size = answer.body.byteLength;
  if (size > keptBudgetBytes) return;
  forgetAnswer(key);
  if (answers.size >= MAX_KEPT_ANSWERS || keptBytes + size > keptBudgetBytes) {
    const now = Date.now();
    for (const [name, kept] of answers) {
      if (kept.until <= now) forgetAnswer(name);
    }
  }
  for (const name of answers.keys()) {
    if (answers.size < MAX_KEPT_ANSWERS && keptBytes + size <= keptBudgetBytes) break;
    forgetAnswer(name);
  }
  answers.set(key, answer);
  keptBytes += size;
}

/** A Maps proxy's GET, with the guard above. */
export function mapsRoute(name: string, handler: Handler, options: MapsRouteOptions) {
  return async function GET(req: Request): Promise<Response> {
    const gate = await requireSignedIn(req);
    if (gate.refused) return gate.refused;
    if (!allowed(`${name}:${gate.user.userId}`, options.perMinute)) {
      return NextResponse.json(
        { error: 'Too many requests' },
        { status: 429, headers: { 'Retry-After': '60', 'Cache-Control': 'private, no-store' } },
      );
    }
    if (!options.cacheSeconds) {
      const res = await handler(req);
      return new Response(res.body, { status: res.status, headers: privateHeaders(res.headers) });
    }
    const key = answerKey(name, req);
    const kept = answers.get(key);
    if (kept && kept.until > Date.now()) {
      return new Response(kept.body.slice(0), { status: kept.status, headers: kept.headers });
    }
    if (kept) forgetAnswer(key);
    const res = await handler(req);
    const headers = privateHeaders(res.headers);
    if (res.status !== 200) {
      return new Response(res.body, { status: res.status, headers });
    }
    const body = await res.arrayBuffer();
    if (body.byteLength <= MAX_KEPT_BYTES) {
      keepAnswer(key, {
        until: Date.now() + options.cacheSeconds * 1000,
        status: res.status,
        headers: [...headers.entries()],
        body,
      });
    }
    return new Response(body.slice(0), { status: res.status, headers });
  };
}
