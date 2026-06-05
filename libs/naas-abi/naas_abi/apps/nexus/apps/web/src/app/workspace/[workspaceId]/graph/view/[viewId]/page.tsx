'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import { AlertCircle, Loader2, Network } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { NetworkViewExportMenu } from '@/components/graph/network-view-export-menu';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import {
  useKnowledgeGraphStore,
  type NetworkViewState,
} from '@/stores/knowledge-graph';
import {
  NetworkPane,
  type ApiGraphInfo,
  type ApiGraphKpis,
  type NetworkExportContext,
} from '@/components/graph/network-pane';

interface SavedViewResponse {
  id: string;
  label: string;
  name?: string;
  view_type?: string;
  kind?: string;
  visibility?: string;
  graph_id?: string;
  graph_uri?: string;
  state?: NetworkViewState;
}

export default function GraphViewPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const viewId = params.viewId as string;

  const { setActiveSavedView, setVisibleGraphs } = useKnowledgeGraphStore();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<SavedViewResponse | null>(null);
  const [activeGraph, setActiveGraph] = useState<ApiGraphInfo | null>(null);
  const [kpis, setKpis] = useState<ApiGraphKpis | null>(null);
  const [exportContext, setExportContext] = useState<NetworkExportContext | null>(null);

  const initialState = useMemo<NetworkViewState | null>(() => {
    if (!view?.state) return null;
    return {
      selectedClassIds: view.state.selectedClassIds ?? [],
      selectedPropUris: view.state.selectedPropUris ?? {},
      activeBuckets: view.state.activeBuckets ?? [],
      hiddenNodeIds: view.state.hiddenNodeIds ?? [],
    };
  }, [view]);

  const loadView = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await authFetch(
        `${getApiUrl()}/api/view/${encodeURIComponent(viewId)}?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!response.ok) {
        throw new Error(`Failed to load view (${response.status})`);
      }
      const data = (await response.json()) as SavedViewResponse;
      setView(data);
      setActiveSavedView(data.id);
      const graphUri = data.graph_uri ?? data.state?.graphUri;
      if (data.graph_id) {
        setVisibleGraphs([data.graph_id]);
      }
      if (data.graph_id && graphUri) {
        setActiveGraph({
          id: data.graph_id,
          uri: graphUri,
          label: data.label ?? data.name ?? data.graph_id,
        });
      } else {
        throw new Error('View is missing graph metadata');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load view');
      setView(null);
      setActiveGraph(null);
    } finally {
      setLoading(false);
    }
  }, [setActiveSavedView, setVisibleGraphs, viewId, workspaceId]);

  useEffect(() => {
    void loadView();
  }, [loadView]);

  useEffect(() => {
    if (!activeGraph) {
      setKpis(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch(
          `${getApiUrl()}/api/graph/kpis?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}`
        );
        if (!res.ok) return;
        const data = (await res.json()) as ApiGraphKpis;
        if (!cancelled) setKpis(data);
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, activeGraph]);

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex h-10 items-center justify-between border-b bg-muted/30 px-4">
            <div className="flex items-center gap-2 rounded-md bg-background px-3 py-1 text-sm">
              <Network size={14} />
              Network
            </div>
            <NetworkViewExportMenu
              workspaceId={workspaceId}
              triples={exportContext?.triples ?? []}
              onExportExcel={() => exportContext?.exportExcel()}
              disabled={!exportContext}
            />
          </div>
          <div className="flex flex-1 overflow-hidden">
            {loading ? (
              <div className="flex flex-1 items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="max-w-md text-center">
                  <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
                  <p className="text-sm">{error}</p>
                </div>
              </div>
            ) : activeGraph && initialState ? (
              <NetworkPane
                workspaceId={workspaceId}
                activeGraph={activeGraph}
                kpis={kpis}
                initialState={initialState}
                onExportContextChange={setExportContext}
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
