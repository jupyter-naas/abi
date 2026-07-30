import { readFile } from 'node:fs/promises';
import path from 'node:path';

import { mapsJson, mapsPinResponse } from '../_lib';

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
};

/**
 * Zen tip Custom layer: Ontologist, North America.
 * Prefers the synced pins JSON under maps/lib; falls back to Zen API when set.
 */
export async function GET() {
  try {
    const localPath = path.join(
      process.cwd(),
      'src/app/workspace/[workspaceId]/maps/lib/ontologist-north-america.pins.json',
    );
    try {
      const raw = await readFile(localPath, 'utf8');
      const data = JSON.parse(raw) as PinsPayload;
      const pins = Array.isArray(data.pins) ? data.pins : [];
      return mapsPinResponse(pins, {
        source: data.source ?? 'intelligence/ontologist-north-america',
        layer_title: data.layer_title ?? 'Ontologist, North America',
        observation_date: data.observation_date ?? '2026-07-31',
      });
    } catch {
      // fall through to API proxy
    }

    const apiHost =
      process.env.PUBLIC_API_HOST ||
      process.env.NEXT_PUBLIC_API_HOST ||
      '127.0.0.1:9879';
    const base = apiHost.startsWith('http') ? apiHost : `http://${apiHost}`;
    const res = await fetch(`${base}/api/intelligence/ontologist-north-america`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(15000),
    });
    const data = (await res.json()) as PinsPayload;
    if (!res.ok) {
      return mapsJson(
        {
          error: data.message || `Intelligence API ${res.status}`,
          pins: [],
          count: 0,
        },
        { status: 502 },
      );
    }
    const pins = Array.isArray(data.pins) ? data.pins : [];
    return mapsPinResponse(pins, {
      source: data.source ?? 'intelligence/ontologist-north-america',
      layer_title: data.layer_title,
      observation_date: data.observation_date,
      empty: data.empty,
      message: data.message,
    });
  } catch (err) {
    return mapsJson(
      {
        error:
          err instanceof Error
            ? err.message
            : 'Ontologist North America feed failed',
        pins: [],
        count: 0,
        empty: true,
      },
      { status: 502 },
    );
  }
}
