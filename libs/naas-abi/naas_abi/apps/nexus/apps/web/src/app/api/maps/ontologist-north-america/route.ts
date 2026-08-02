import { mapsJson } from '../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type PinsPayload = {
  pins?: Array<Record<string, unknown>>;
  count?: number;
  source?: string;
  layer_title?: string;
  observation_date?: string;
  empty?: boolean;
  message?: string;
  detail?: string;
  error?: string;
};

function authJson(
  body: unknown,
  status: number,
): Response {
  return mapsJson(body, { status, cacheSeconds: 0 });
}

/**
 * Ontologist, North America pins.
 * Requires Nexus Bearer auth + workspace_id; proxies the gated intelligence API.
 * Does not serve a local PII pins file.
 */
export async function GET(request: Request) {
  const auth = request.headers.get('authorization');
  if (!auth?.toLowerCase().startsWith('bearer ')) {
    return authJson(
      { error: 'Not authenticated', pins: [], count: 0 },
      401,
    );
  }

  const url = new URL(request.url);
  const workspaceId = (url.searchParams.get('workspace_id') || '').trim();
  if (!workspaceId) {
    return authJson(
      { error: 'workspace_id required', pins: [], count: 0 },
      400,
    );
  }

  try {
    const apiHost =
      process.env.NEXUS_API_URL ||
      process.env.PUBLIC_API_HOST ||
      process.env.NEXT_PUBLIC_API_HOST ||
      process.env.NEXT_PUBLIC_API_URL ||
      '127.0.0.1:9879';
    const base = apiHost.startsWith('http') ? apiHost : `http://${apiHost}`;
    const target = new URL(`${base}/api/intelligence/ontologist-north-america`);
    target.searchParams.set('workspace_id', workspaceId);

    const res = await fetch(target.toString(), {
      cache: 'no-store',
      headers: { Authorization: auth },
      signal: AbortSignal.timeout(15000),
    });
    const data = (await res.json()) as PinsPayload;
    if (res.status === 401 || res.status === 403) {
      return authJson(
        {
          error: data.detail || data.error || data.message || 'Not authenticated',
          pins: [],
          count: 0,
        },
        res.status,
      );
    }
    if (!res.ok) {
      return authJson(
        {
          error: data.message || data.error || `Intelligence API ${res.status}`,
          pins: [],
          count: 0,
        },
        502,
      );
    }
    const pins = Array.isArray(data.pins) ? data.pins : [];
    return mapsJson(
      {
        pins,
        count: pins.length,
        source: data.source ?? 'intelligence/ontologist-north-america',
        layer_title: data.layer_title,
        observation_date: data.observation_date,
        empty: data.empty,
        message: data.message,
      },
      { cacheSeconds: 0 },
    );
  } catch (err) {
    return authJson(
      {
        error:
          err instanceof Error
            ? err.message
            : 'Ontologist North America feed failed',
        pins: [],
        count: 0,
        empty: true,
      },
      502,
    );
  }
}
