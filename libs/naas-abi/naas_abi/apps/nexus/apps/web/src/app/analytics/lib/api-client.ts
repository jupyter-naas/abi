/**
 * Server-side helper for proxying analytics requests to the Nexus API.
 *
 * The Nexus API analytics router is mounted at /api/analytics
 * (see libs/naas-abi/naas_abi/apps/nexus/apps/api/app/api/router.py)
 * and is backed by a SPARQL secondary adapter over the platform
 * ontology + the checked-in fake-data TTL. The adapter re-parses the
 * TTL files whenever their mtime changes, so editing the TTL and
 * refreshing the browser is enough to see KPIs update.
 *
 * URL resolution order (server-side):
 *   1. ANALYTICS_API_URL            — analytics-specific override
 *   2. NEXUS_API_URL_INTERNAL       — generic server-side override
 *   3. NEXUS_API_URL                — only if it looks reachable from
 *                                     Node (e.g. http://localhost:...)
 *   4. http://localhost:9879        — the API's default listen address
 *
 * NEXUS_API_URL is intentionally LOW priority because in many local
 * setups it points at the browser-facing reverse-proxy URL
 * (e.g. https://api.localhost), which Node's fetch cannot resolve.
 */

const DEFAULT_API_URL = 'http://localhost:9879';

function isNodeReachable(u: string | undefined): u is string {
  if (!u) return false;
  try {
    const host = new URL(u).hostname;
    // Reverse-proxy hostnames like *.localhost don't resolve via Node DNS.
    // Bare 'localhost', 127.x, and explicit IPs do.
    if (host === 'localhost') return true;
    if (/^\d+\.\d+\.\d+\.\d+$/.test(host)) return true;
    return !host.endsWith('.localhost');
  } catch {
    return false;
  }
}

function baseUrl(): string {
  const candidates = [
    process.env.ANALYTICS_API_URL,
    process.env.NEXUS_API_URL_INTERNAL,
    isNodeReachable(process.env.NEXUS_API_URL) ? process.env.NEXUS_API_URL : undefined,
    DEFAULT_API_URL,
  ];
  return (candidates.find(Boolean) as string).replace(/\/$/, '');
}

function forwardSearch(reqUrl: string): string {
  const incoming = new URL(reqUrl);
  const out = new URLSearchParams();
  for (const k of ['start_date', 'end_date', 'user_email', 'workspace_id', 'limit']) {
    const v = incoming.searchParams.get(k);
    if (v !== null && v !== '' && v !== 'all') out.set(k, v);
  }
  const s = out.toString();
  return s ? `?${s}` : '';
}

export async function analyticsFetch(path: string, reqUrl: string): Promise<Response> {
  const url = `${baseUrl()}/api/analytics${path}${forwardSearch(reqUrl)}`;
  return fetch(url, {
    method: 'GET',
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  });
}

export async function passthrough(path: string, reqUrl: string): Promise<Response> {
  const target = baseUrl();
  try {
    const res = await analyticsFetch(path, reqUrl);
    const text = await res.text();
    return new Response(text, {
      status: res.status,
      headers: {
        'Content-Type': res.headers.get('Content-Type') ?? 'application/json',
      },
    });
  } catch (err) {
    return Response.json(
      {
        error: 'Analytics service unreachable',
        detail: String(err),
        hint:
          `Tried ${target}/api/analytics${path}. Set ANALYTICS_API_URL or ` +
          `NEXUS_API_URL_INTERNAL to a Node-reachable URL (e.g. http://localhost:9879 ` +
          `or http://nexus-api:9879 in Docker).`,
        url: target,
      },
      { status: 502 },
    );
  }
}
