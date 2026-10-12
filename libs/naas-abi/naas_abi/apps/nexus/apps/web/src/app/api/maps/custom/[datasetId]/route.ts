import { getMapsCustomDataset } from '@/lib/maps-custom-datasets';
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

/**
 * Authed proxy for a deployment-registered Custom Maps dataset.
 *
 * The target comes from NEXT_PUBLIC_MAPS_CUSTOM_DATASETS keyed by `datasetId`,
 * never from the request, and the descriptor's endpoint is validated to be a
 * Nexus API path — so the caller's Bearer token is only ever forwarded on-host.
 * Custom layers may carry private data, so this always requires Bearer auth plus
 * a workspace_id and is never cached.
 */
export async function GET(
  request: Request,
  { params }: { params: { datasetId: string } },
) {
  const dataset = getMapsCustomDataset(params.datasetId);
  if (!dataset) {
    return errorJson({ error: 'Unknown dataset' }, 404);
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

  try {
    const target = new URL(`${nexusInternalApiBase()}${dataset.endpoint}`);
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
