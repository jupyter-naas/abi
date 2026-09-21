"use client";
import {useEffect, useState} from 'react';
import {getApiUrl} from '@/lib/config';
import {useAuthStore} from '@/stores/auth';
import {useWorkspaceStore} from '@/stores/workspace';
import {MAPS_DATASETS, type MapsDataset} from './datasets';

export interface GraphMapDataset extends MapsDataset { graphUri: string; runtime: true; }

export function useGraphMapLayers() {
  const workspaceId = useWorkspaceStore(s => s.currentWorkspaceId);
  const token = useAuthStore(s => s.token);
  const [state, setState] = useState<{workspaceId:string|null; token:string|null; layers:GraphMapDataset[]; loading:boolean; error:string|null}>({workspaceId:null,token:null,layers:[],loading:true,error:null});
  useEffect(() => {
    const controller = new AbortController();
    setState({workspaceId,token,layers:[],loading:true,error:null});
    if (!workspaceId || !token) return () => controller.abort();
    fetch(`${getApiUrl()}/api/maps/layers?workspace_id=${encodeURIComponent(workspaceId)}`, {headers:{Authorization:`Bearer ${token}`}, cache:'no-store',signal:controller.signal})
      .then(async res => {
        if (res.status === 404) return {layers:[]};
        if (!res.ok) throw new Error('Unable to load graph map layers');
        return res.json();
      }).then(data => {
        const ids = new Set(MAPS_DATASETS.map(d => d.id));
        const layers = (Array.isArray(data.layers) ? data.layers : []).filter((d: GraphMapDataset) => d && typeof d.id === 'string' && /^[a-z0-9][a-z0-9-]*$/.test(d.id) && typeof d.title === 'string' && typeof d.graphUri === 'string' && !ids.has(d.id));
        if (!controller.signal.aborted) setState({workspaceId,token,layers,loading:false,error:null});
      }).catch(error => {if (!controller.signal.aborted) setState({workspaceId,token,layers:[],loading:false,error:String(error.message)});});
    return () => controller.abort();
  }, [workspaceId,token]);
  return state.workspaceId === workspaceId && state.token === token ? state : {layers:[],loading:true,error:null};
}
