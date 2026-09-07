'use client';

import { useParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import type { MapsCustomDataset } from '@/lib/maps-custom-datasets';
import { mapsCustomFeedUrl } from '../lib/datasets';
import { fetchMapsFeedPins } from '../lib/maps-feed';
import { MapsFeedCanvas } from './maps-feed-canvas';

/**
 * Canvas for a deployment-registered Custom dataset. Everything product-specific
 * (title, copy, endpoint) comes from the descriptor, so upstream ABI carries the
 * mechanism and no particular layer.
 */
export function MapsCustomFeed({ dataset }: { dataset: MapsCustomDataset }) {
  const params = useParams();
  const workspaceId =
    typeof params?.workspaceId === 'string' ? params.workspaceId : '';

  return (
    <MapsFeedCanvas
      title={dataset.title}
      loadingLabel={`Loading ${dataset.title}…`}
      readyMeta={(n) =>
        dataset.metaLabel
          ? dataset.metaLabel.replace('{count}', String(n))
          : `${n} points`
      }
      emptyTitle={dataset.emptyTitle ?? 'No data'}
      emptyBody={
        dataset.emptyBody ??
        'This feed returned no mappable points right now. Check that the configured backend is reachable.'
      }
      sourceHref={
        workspaceId ? mapsCustomFeedUrl(dataset.id, workspaceId) : undefined
      }
      sourceLabel={dataset.sourceLabel ?? 'Source (auth)'}
      fetchPins={async (signal) => {
        if (!workspaceId) {
          throw new Error('Missing workspace');
        }
        const token = useAuthStore.getState().token;
        if (!token) {
          throw new Error('Not authenticated');
        }
        const { pins } = await fetchMapsFeedPins(
          mapsCustomFeedUrl(dataset.id, workspaceId),
          signal,
          { Authorization: `Bearer ${token}` },
        );
        return pins;
      }}
      fitMaxZoom={dataset.fitMaxZoom ?? 5}
    />
  );
}
