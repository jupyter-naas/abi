import { isMapsFeatureCollection } from '@/app/workspace/[workspaceId]/maps/lib/maps-pin-geojson';

import { mapsFeedResponse, mapsPinResponse, nexusInternalApiBase } from '../../_lib';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type FeedPayload = {
  type?: string;
  features?: Array<Record<string, unknown>>;
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

function errorJson(body: Record<string, unknown>, status: number): Response {
  return mapsPinResponse([], body, { status, cacheSeconds: 0 });
}

const LAYER_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,47}$/;

/** Same check as the API's is_nexus_api_path: the token must stay on-host. */
function isNexusApiFeedPath(value: unknown): value is string {
  return (
    typeof value === 'string'
    && value.startsWith('/api/')
    && !value.includes('//')
    && !value.includes('..')
    && !value.includes('\\')
    && !/\s/.test(value)
    && value.length <= 500
  );
}

type FeedLayerRecord = { title?: string; feed_type?: string; feed_url?: string };

/**
 * Authed proxy for a feed layer record (Settings → Maps, `feed_type: geojson_url`).
 *
 * The target is the record's `feed_url`, read from `/api/maps/layouts/{id}`
 * with the caller's token (so workspace membership is checked there), never
 * from this request; it must be a Nexus API path, so the Bearer token is only
 * ever forwarded on-host. Layers may carry private data: always authed, never
 * cached.
 */
export async function GET(
  request: Request,
  { params }: { params: { datasetId: string } },
) {
  if (!LAYER_ID_PATTERN.test(params.datasetId)) {
    return errorJson({ error: 'Unknown layer' }, 404);
  }

  const auth = request.headers.get('authorization');
  if (!auth?.toLowerCase().startsWith('bearer ')) {
    return errorJson({ error: 'Not authenticated' }, 401);
  }

  const url = new URL(request.url);
  const workspaceId = (url.searchParams.get('workspace_id') || '').trim();
  if (!workspaceId) {
    return errorJson({ error: 'workspace_id required' }, 400);
  }

  const base = nexusInternalApiBase();
  let dataset: { title: string; endpoint: string };
  try {
    const recordUrl = new URL(`${base}/api/maps/layouts/${encodeURIComponent(params.datasetId)}`);
    recordUrl.searchParams.set('workspace_id', workspaceId);
    const recordRes = await fetch(recordUrl.toString(), {
      cache: 'no-store',
      headers: { Authorization: auth },
      signal: AbortSignal.timeout(10000),
    });
    if (!recordRes.ok) {
      const status = [401, 403, 404].includes(recordRes.status) ? recordRes.status : 502;
      return errorJson({ error: `Layer lookup failed (${recordRes.status})` }, status);
    }
    const record = (await recordRes.json()) as FeedLayerRecord;
    if (record.feed_type !== 'geojson_url' || !isNexusApiFeedPath(record.feed_url)) {
      return errorJson({ error: 'Not a feed layer' }, 404);
    }
    dataset = { title: record.title || params.datasetId, endpoint: record.feed_url };
  } catch (err) {
    return errorJson({ error: err instanceof Error ? err.message : 'Layer lookup failed' }, 502);
  }

  try {
    const target = new URL(`${base}${dataset.endpoint}`);
    target.searchParams.set('workspace_id', workspaceId);

    const res = await fetch(target.toString(), {
      cache: 'no-store',
      headers: { Authorization: auth },
      signal: AbortSignal.timeout(15000),
    });
    const data = (await res.json()) as FeedPayload;
    if (res.status === 401 || res.status === 403) {
      return errorJson(
        {
          error: data.detail || data.error || data.message || 'Not authenticated',
        },
        res.status,
      );
    }
    if (!res.ok) {
      return errorJson(
        {
          error: data.message || data.error || `${dataset.title} feed ${res.status}`,
        },
        502,
      );
    }
    if (isMapsFeatureCollection(data)) {
      return mapsFeedResponse(
        {
          ...data,
          source: data.source ?? dataset.endpoint,
          layer_title: data.layer_title ?? dataset.title,
          observation_date: data.observation_date,
          empty: data.empty,
          message: data.message,
        },
        { cacheSeconds: 0 },
      );
    }
    const pins = Array.isArray(data.pins) ? data.pins : [];
    return mapsPinResponse(
      pins,
      {
        source: data.source ?? dataset.endpoint,
        layer_title: data.layer_title ?? dataset.title,
        observation_date: data.observation_date,
        empty: data.empty,
        message: data.message,
      },
      { cacheSeconds: 0 },
    );
  } catch (err) {
    return errorJson(
      {
        error:
          err instanceof Error ? err.message : `${dataset.title} feed failed`,
        empty: true,
      },
      502,
    );
  }
}
