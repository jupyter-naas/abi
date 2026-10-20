"use client";
import {useParams} from 'next/navigation';
import {getApiUrl} from '@/lib/config';
import {useAuthStore} from '@/stores/auth';
import {fetchMapsFeedPins} from '../lib/maps-feed';
import type {GraphMapDataset} from '../lib/use-graph-map-layers';
import {MapsFeedCanvas} from './maps-feed-canvas';

export function MapsGraphFeed({dataset}: {dataset:GraphMapDataset}) {
  const {workspaceId} = useParams<{workspaceId:string}>();
  const fetchPins = async (signal:AbortSignal) => {
    const token = useAuthStore.getState().token;
    if (!token) throw new Error('Not authenticated');
    const url = `${getApiUrl()}/api/maps/layers/${encodeURIComponent(dataset.id)}?workspace_id=${encodeURIComponent(workspaceId)}`;
    return fetchMapsFeedPins(url, signal, {Authorization:`Bearer ${token}`});
  };
  return <MapsFeedCanvas key={`${workspaceId}:${dataset.id}:${dataset.graphUri}`} title={dataset.title} loadingLabel="Loading graph locations…" readyMeta={n => `${n} locations`} emptyBody="No mappable records were found in this graph snapshot." fetchPins={fetchPins} inspectable workspaceId={workspaceId} />;
}
