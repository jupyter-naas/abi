'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Header } from '@/components/shell/header';
import {
  AlertCircle,
  ChevronDown,
  Download,
  Loader2,
  RefreshCw,
  Save,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { authFetch } from '@/stores/auth';
import {
  useKnowledgeGraphStore,
  type NetworkViewState,
  GRAPH_NETWORK_RESET_EVENT,
} from '@/stores/knowledge-graph';
import { SaveNetworkViewDialog } from '@/components/graph/save-network-view-dialog';
import { GraphSectionNav } from '@/components/graph/graph-section-nav';
import {
  NetworkPane,
  type ApiGraphInfo,
  type ApiGraphKpis,
  type NetworkExportContext,
} from '@/components/graph/network-pane';

interface ApiGraphPack {
  role_label: string;
  graphs: ApiGraphInfo[];
}

function isSystemGraph(graph: { id: string; label?: string }): boolean {
  const id = graph.id.trim().toLowerCase();
  const name = (graph.label ?? '').trim().toLowerCase();
  return (
    id === 'schema' ||
    id === 'nexus' ||
    id.endsWith('/schema') ||
    id.endsWith('/nexus') ||
    name === 'schema' ||
    name === 'nexus'
  );
}

export default function NetworkPage() {
  const params = useParams();
  const router = useRouter();
  const workspaceId = params.workspaceId as string;

  const {
    selectedGraphId,
    visibleGraphIds,
    setActiveSavedView,
  } = useKnowledgeGraphStore();

  const [graphPacks, setGraphPacks] = useState<ApiGraphPack[]>([]);
  const [graphsLoading, setGraphsLoading] = useState(true);
  const [graphsError, setGraphsError] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<'ttl' | 'owl' | 'nt'>('ttl');
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [kpis, setKpis] = useState<ApiGraphKpis | null>(null);
  const [networkState, setNetworkState] = useState<NetworkViewState | null>(null);
  const [exportContext, setExportContext] = useState<NetworkExportContext | null>(null);
  const [showSaveViewDialog, setShowSaveViewDialog] = useState(false);
  const [saveViewName, setSaveViewName] = useState('');
  const [saveViewType, setSaveViewType] = useState('Unknown');
  const [existingViewTypes, setExistingViewTypes] = useState<string[]>(['Unknown']);
  const [saveViewVisibility, setSaveViewVisibility] = useState<'workspace' | 'personal'>('workspace');
  const [savingView, setSavingView] = useState(false);
  const [selectionResetKey, setSelectionResetKey] = useState(0);

  const allGraphs = useMemo<ApiGraphInfo[]>(() => {
    const seen = new Set<string>();
    const out: ApiGraphInfo[] = [];
    for (const pack of graphPacks) {
      for (const g of pack.graphs) {
        if (seen.has(g.uri)) continue;
        seen.add(g.uri);
        out.push(g);
      }
    }
    return out;
  }, [graphPacks]);

  const activeGraph = useMemo<ApiGraphInfo | null>(() => {
    if (selectedGraphId) {
      const match = allGraphs.find((g) => g.id === selectedGraphId);
      if (match) return match;
    }
    if (visibleGraphIds.length > 0) {
      const match = allGraphs.find((g) => visibleGraphIds.includes(g.id));
      if (match) return match;
    }
    return allGraphs.find((g) => !isSystemGraph(g)) ?? allGraphs[0] ?? null;
  }, [allGraphs, selectedGraphId, visibleGraphIds]);

  const loadGraphs = useCallback(async () => {
    setGraphsLoading(true);
    setGraphsError(null);
    try {
      const res = await authFetch(
        `${getApiUrl()}/api/graph/list?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!res.ok) throw new Error(`Failed to load graphs (${res.status})`);
      const data = (await res.json()) as ApiGraphPack[];
      setGraphPacks(Array.isArray(data) ? data : []);
    } catch (err) {
      setGraphsError(err instanceof Error ? err.message : 'Failed to load graphs');
      setGraphPacks([]);
    } finally {
      setGraphsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadGraphs();
  }, [loadGraphs]);

  const resetNetworkSelection = useCallback(() => {
    setNetworkState(null);
    setExportContext(null);
    setSelectionResetKey((key) => key + 1);
  }, []);

  useEffect(() => {
    const onReset = () => resetNetworkSelection();
    window.addEventListener(GRAPH_NETWORK_RESET_EVENT, onReset);
    return () => window.removeEventListener(GRAPH_NETWORK_RESET_EVENT, onReset);
  }, [resetNetworkSelection]);

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

  const handleExport = useCallback(async () => {
    if (!activeGraph || exporting) return;
    setExporting(true);
    try {
      const url = `${getApiUrl()}/api/graph/export?workspace_id=${encodeURIComponent(workspaceId)}&graph_uri=${encodeURIComponent(activeGraph.uri)}&format=${exportFormat}`;
      const response = await authFetch(url);
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const blob = await response.blob();
      const filename = `${activeGraph.label || 'graph'}.${exportFormat}`;
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      console.error('Export failed', err);
    } finally {
      setExporting(false);
    }
  }, [activeGraph, exporting, workspaceId, exportFormat]);

  const handleSaveView = useCallback(async () => {
    const name = saveViewName.trim();
    if (!name || !activeGraph || !networkState || networkState.selectedClassIds.length === 0) return;
    setSavingView(true);
    try {
      const response = await authFetch(`${getApiUrl()}/api/view`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: workspaceId,
          name,
          view_type: saveViewType.trim() || 'Unknown',
          kind: 'network',
          visibility: 'workspace',
          graph_id: activeGraph.id,
          graph_uri: activeGraph.uri,
          state: {
            ...networkState,
            graphUri: activeGraph.uri,
          },
        }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        console.error('Failed to save view:', err);
        return;
      }
      const data = (await response.json()) as { view_id?: string };
      if (data.view_id) {
        setActiveSavedView(data.view_id);
        window.dispatchEvent(new CustomEvent('view-list-update'));
        router.push(`/workspace/${workspaceId}/graph/view/${encodeURIComponent(data.view_id)}`);
      }
      setShowSaveViewDialog(false);
      setSaveViewName('');
    } catch (error) {
      console.error('Failed to save view:', error);
    } finally {
      setSavingView(false);
    }
  }, [
    activeGraph,
    networkState,
    router,
    saveViewName,
    saveViewType,
    setActiveSavedView,
    workspaceId,
  ]);

  const loadExistingViewTypes = useCallback(async () => {
    try {
      const response = await authFetch(
        `${getApiUrl()}/api/view/list?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      if (!response.ok) return;
      const data = (await response.json()) as Array<{ view_type?: string }>;
      const types = new Set<string>(['Unknown']);
      for (const item of data) {
        const label = (item.view_type ?? 'Unknown').trim() || 'Unknown';
        types.add(label);
      }
      setExistingViewTypes(Array.from(types).sort((a, b) => a.localeCompare(b)));
    } catch {
      setExistingViewTypes(['Unknown']);
    }
  }, [workspaceId]);

  const saveViewButton = networkState && networkState.selectedClassIds.length > 0 ? (
    <button
      type="button"
      onClick={() => {
        setSaveViewName(`View ${new Date().toLocaleDateString()}`);
        setSaveViewType('Unknown');
        setSaveViewVisibility('workspace');
        void loadExistingViewTypes();
        setShowSaveViewDialog(true);
      }}
      className="flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
      title="Save current selection as a view"
    >
      <Save size={12} />
      Save view
    </button>
  ) : null;

  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <div className="flex flex-1 flex-col overflow-hidden">
          <GraphSectionNav
            workspaceId={workspaceId}
            active="network"
            trailing={
              <div className="relative flex items-center">
                <button
                  type="button"
                  onClick={() => void handleExport()}
                  disabled={!activeGraph || exporting}
                  className={cn(
                    'flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground',
                    (!activeGraph || exporting) && 'cursor-not-allowed opacity-50'
                  )}
                  title={!activeGraph ? 'Select a graph to export' : `Export graph as .${exportFormat}`}
                >
                  {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                  {exporting ? 'Exporting...' : 'Export'}
                </button>
                <button
                  type="button"
                  onClick={() => setExportMenuOpen((o) => !o)}
                  disabled={!activeGraph}
                  className={cn(
                    'ml-0.5 flex items-center rounded px-1 py-0.5 text-muted-foreground hover:text-foreground',
                    !activeGraph && 'cursor-not-allowed opacity-50'
                  )}
                  title="Select export format"
                >
                  <ChevronDown size={12} />
                </button>
                {exportMenuOpen && (
                  <div className="absolute right-0 top-full z-50 mt-1 min-w-[90px] rounded-md border bg-background shadow-md">
                    {(['ttl', 'owl', 'nt'] as const).map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        onClick={() => {
                          setExportFormat(fmt);
                          setExportMenuOpen(false);
                        }}
                        className={cn(
                          'flex w-full items-center px-3 py-1.5 text-left text-sm hover:bg-muted',
                          exportFormat === fmt && 'font-medium text-foreground'
                        )}
                      >
                        .{fmt}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            }
          />
          <div className="flex flex-1 overflow-hidden">
            {graphsLoading ? (
              <div className="flex flex-1 items-center justify-center">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            ) : graphsError ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="max-w-md text-center">
                  <AlertCircle size={32} className="mx-auto mb-3 text-red-500" />
                  <p className="mb-2 text-sm">{graphsError}</p>
                  <button
                    onClick={() => void loadGraphs()}
                    className="mx-auto flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
                  >
                    <RefreshCw size={14} />
                    Retry
                  </button>
                </div>
              </div>
            ) : !activeGraph ? (
              <div className="flex flex-1 items-center justify-center">
                <p className="text-sm text-muted-foreground">No graphs available in this workspace.</p>
              </div>
            ) : (
              <NetworkPane
                key={`${activeGraph.uri}-${selectionResetKey}`}
                workspaceId={workspaceId}
                activeGraph={activeGraph}
                kpis={kpis}
                onExportContextChange={setExportContext}
                headerActions={saveViewButton}
                onStateSnapshot={(state) => setNetworkState(state)}
              />
            )}
          </div>
        </div>
      </div>

      {showSaveViewDialog && (
        <SaveNetworkViewDialog
          name={saveViewName}
          viewType={saveViewType}
          existingViewTypes={existingViewTypes}
          visibility={saveViewVisibility}
          saving={savingView}
          onNameChange={setSaveViewName}
          onViewTypeChange={setSaveViewType}
          onVisibilityChange={setSaveViewVisibility}
          onSave={() => void handleSaveView()}
          onCancel={() => {
            setShowSaveViewDialog(false);
            setSaveViewName('');
          }}
        />
      )}
    </div>
  );
}
