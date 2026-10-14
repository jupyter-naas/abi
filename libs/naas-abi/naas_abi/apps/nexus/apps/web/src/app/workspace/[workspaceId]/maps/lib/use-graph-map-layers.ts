"use client";
import {useEffect, useState} from 'react';
import {getApiUrl} from '@/lib/config';
import {useAuthStore} from '@/stores/auth';
import {useWorkspaceStore} from '@/stores/workspace';
import {MAPS_DATASETS, type MapsDataset} from './datasets';

export interface GraphMapDataset extends MapsDataset { graphUri: string; runtime: true; }

type GraphLayersState = {layers: GraphMapDataset[]; loading: boolean; error: string | null};

/**
 * One request per workspace (and token) for every component that lists the
 * layers, kept a minute: graph layers only change when a module registers one.
 * Failures are not kept.
 */
const TTL_MS = 60_000;
const loads = new Map<string, {at: number; promise: Promise<GraphMapDataset[]>}>();

function loadGraphLayers(workspaceId: string, token: string): Promise<GraphMapDataset[]> {
  const key = `${workspaceId}\n${token}`;
  const cached = loads.get(key);
  if (cached && Date.now() - cached.at < TTL_MS) return cached.promise;
  const promise = fetch(`${getApiUrl()}/api/maps/layers?workspace_id=${encodeURIComponent(workspaceId)}`, {headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'})
    .then(async res => {
      if (res.status === 404) return {layers: []};
      if (!res.ok) throw new Error('Unable to load graph map layers');
      return res.json();
    })
    .then(data => {
      const ids = new Set(MAPS_DATASETS.map(d => d.id));
      return (Array.isArray(data.layers) ? data.layers : []).filter((d: GraphMapDataset) => d && typeof d.id === 'string' && /^[a-z0-9][a-z0-9-]*$/.test(d.id) && typeof d.title === 'string' && typeof d.graphUri === 'string' && !ids.has(d.id));
    });
  const entry = {at: Date.now(), promise};
  loads.set(key, entry);
  promise.catch(() => { if (loads.get(key) === entry) loads.delete(key); });
  return promise;
}

export function useGraphMapLayers(): GraphLayersState {
  const workspaceId = useWorkspaceStore(s => s.currentWorkspaceId);
  const token = useAuthStore(s => s.token);
  const [state, setState] = useState<GraphLayersState & {workspaceId: string | null; token: string | null}>({workspaceId: null, token: null, layers: [], loading: true, error: null});
  useEffect(() => {
    let cancelled = false;
    setState({workspaceId, token, layers: [], loading: true, error: null});
    if (!workspaceId || !token) return () => { cancelled = true; };
    loadGraphLayers(workspaceId, token)
      .then(layers => { if (!cancelled) setState({workspaceId, token, layers, loading: false, error: null}); })
      .catch((error: Error) => { if (!cancelled) setState({workspaceId, token, layers: [], loading: false, error: String(error.message)}); });
    return () => { cancelled = true; };
  }, [workspaceId, token]);
  return state.workspaceId === workspaceId && state.token === token ? state : {layers: [], loading: true, error: null};
}
