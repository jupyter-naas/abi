/**
 * Shared proxy helper for analytics API routes.
 *
 * All analytics route handlers forward requests to the Python Nexus API
 * instead of reading local JSON mirror files. This module centralises the
 * upstream URL resolution and error handling.
 *
 */

const UPSTREAM =
  process.env.NEXUS_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  'http://localhost:9879';

/**
 * Forward a GET request to the Python analytics API and return the response.
 *
 * @param path  Sub-path under `/api/analytics/` (e.g. `"overview"`)
 * @param req   The incoming Next.js request (used to forward query params)
 */
export async function proxyAnalytics(path: string, req: Request): Promise<Response> {
  const url = new URL(req.url);
  const qs = url.searchParams.toString();
  const target = `${UPSTREAM}/api/analytics/${path}${qs ? `?${qs}` : ''}`;

  try {
    const res = await fetch(target, { cache: 'no-store' });
    const data: unknown = await res.json();
    return Response.json(data, { status: res.status });
  } catch {
    return Response.json({ error: 'upstream unreachable' }, { status: 502 });
  }
}
