"use client";
import {useParams} from 'next/navigation';
import {getApiUrl} from '@/lib/config';
import { getAuthHeader, hasSession } from '@/stores/auth';
import {fetchMapsFeedPins} from '../lib/maps-feed';
import type {GraphMapDataset} from '../lib/use-graph-map-layers';
import {MapsFeedCanvas} from './maps-feed-canvas';

export function MapsGraphFeed({dataset}: {dataset:GraphMapDataset}) {
  const {workspaceId} = useParams<{workspaceId:string}>();
  const fetchPins = async (signal:AbortSignal) => {
    if (!hasSession()) throw new Error('Not authenticated');
    const url = `${getApiUrl()}/api/maps/layers/${encodeURIComponent(dataset.id)}?workspace_id=${encodeURIComponent(workspaceId)}`;
    return fetchMapsFeedPins(url, signal, getAuthHeader());
  };
  return <MapsFeedCanvas key={`${workspaceId}:${dataset.id}:${dataset.graphUri}`} title={dataset.title} loadingLabel="Loading graph locations…" readyMeta={n => `${n} locations`} emptyBody="No mappable records were found in this graph snapshot." fetchPins={fetchPins} inspectable workspaceId={workspaceId} />;
}
