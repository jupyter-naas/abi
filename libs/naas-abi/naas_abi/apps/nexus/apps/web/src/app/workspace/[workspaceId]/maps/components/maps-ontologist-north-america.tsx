'use client';

import { useParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

export function MapsOntologistNorthAmerica() {
  const params = useParams();
  const workspaceId =
    typeof params?.workspaceId === 'string' ? params.workspaceId : '';

  return (
    <MapsFeedCanvas
      title="Ontologist, North America"
      loadingLabel="Loading Ontologist pins…"
      readyMeta={(n) =>
        `${n} Ontologists · Sanax observation 2026-07-31 · Zen intelligence`
      }
      emptyTitle="No Ontologist pins"
      emptyBody="Run the Zen intelligence pipeline (make intelligence-pipeline) into private storage, then refresh. Auth and NaasAI workspace membership are required."
      sourceHref={
        workspaceId
          ? `/api/intelligence/ontologist-north-america?workspace_id=${encodeURIComponent(workspaceId)}`
          : undefined
      }
      sourceLabel="Intelligence feed (auth)"
      fetchPins={async (signal) => {
        if (!workspaceId) {
          throw new Error('Missing workspace');
        }
        const token = useAuthStore.getState().token;
        if (!token) {
          throw new Error('Not authenticated');
        }
        const url =
          `${MAPS_PUBLIC_FEEDS.ontologistNorthAmerica}` +
          `?workspace_id=${encodeURIComponent(workspaceId)}`;
        const { pins } = await fetchMapsFeedPins(url, signal, {
          Authorization: `Bearer ${token}`,
        });
        return pins;
      }}
      fitMaxZoom={4}
    />
  );
}
