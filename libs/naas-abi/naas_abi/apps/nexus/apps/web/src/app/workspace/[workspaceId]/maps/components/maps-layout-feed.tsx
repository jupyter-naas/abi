'use client';

import { useParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import type { LayoutEntry } from '../lib/layouts';
import { layoutsApi } from '../lib/layouts-api';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

/** Canvas for a workspace layout (Settings → Maps): its SPARQL query's pins. */
export function MapsLayoutFeed({ layout }: { layout: LayoutEntry }) {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const fetchPins = async (signal: AbortSignal) => {
    const token = useAuthStore.getState().token;
    if (!token) throw new Error('Not authenticated');
    return fetchMapsFeedPins(layoutsApi.feedUrl(workspaceId, layout.id), signal, { Authorization: `Bearer ${token}` });
  };
  return (
    <MapsFeedCanvas
      key={`${workspaceId}:${layout.id}`}
      title={layout.title}
      loadingLabel="Running the layout query…"
      readyMeta={(n) => `${n} locations · workspace layout`}
      emptyBody="The layout's query returned no rows with a valid ?lat and ?lng."
      fetchPins={fetchPins}
      inspectable
      workspaceId={workspaceId}
    />
  );
}
