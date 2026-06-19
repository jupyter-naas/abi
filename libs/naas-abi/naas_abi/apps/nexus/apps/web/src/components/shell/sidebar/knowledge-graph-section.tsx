'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Waypoints, MoreVertical, Trash2, Eraser, Plus, Bookmark, Folder,
  Database, User, Users, Table2, ChevronRight, Network, Upload, Download,
} from 'lucide-react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useKnowledgeGraphStore, type GraphView } from '@/stores/knowledge-graph';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { listViews, deleteView, type SavedView } from '@/lib/graph-query/client';
import { useConfirm } from '@/components/ui/dialogs';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

interface GraphItem {
  id: string;
  name: string;
  type: 'workspace' | 'user';
  uri: string;
}

interface GraphPackItem {
  roleLabel: string;
  graphs: GraphItem[];
}

interface GraphApiItem {
  id: string;
  label?: string;
  uri: string;
}

interface GraphPackApiItem {
  role_label?: string;
  graphs: unknown[];
}

function isGraphApiItem(value: unknown): value is GraphApiItem {
  return (
    value != null
    && typeof value === 'object'
    && 'id' in value
    && typeof (value as { id: unknown }).id === 'string'
    && 'uri' in value
    && typeof (value as { uri: unknown }).uri === 'string'
  );
}

function isGraphPackApiItem(value: unknown): value is GraphPackApiItem {
  return (
    value != null
    && typeof value === 'object'
    && 'graphs' in value
    && Array.isArray((value as { graphs: unknown }).graphs)
  );
}

function isSchemaGraph(graph: GraphItem): boolean {
  return (
    graph.name === 'schema'
    || graph.id === 'schema'
    || graph.id.endsWith('/schema')
    || graph.name === 'nexus'
    || graph.id === 'nexus'
    || graph.id.endsWith('/nexus')
  );
}

interface ViewFolderGroup {
  path: string;
  views: SavedView[];
}

/** Group saved views by their folder path so the Composer submenu keeps its folder hierarchy. */
function groupViewsByFolder(views: SavedView[]): ViewFolderGroup[] {
  const byPath = new Map<string, SavedView[]>();
  for (const v of views) {
    const key = v.path ?? '';
    const bucket = byPath.get(key);
    if (bucket) bucket.push(v);
    else byPath.set(key, [v]);
  }
  return [...byPath.entries()]
    .map(([path, vs]) => ({
      path,
      views: vs.sort((a, b) => (a.name ?? a.label).localeCompare(b.name ?? b.label)),
    }))
    .sort((a, b) => a.path.localeCompare(b.path));
}

/** A top-level app entry (Network / Individuals / Composer) with an optional expandable submenu. */
function AppEntry({
  icon,
  label,
  active,
  expandable,
  expanded,
  onToggle,
  onOpen,
  onAdd,
  addTitle,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  expandable: boolean;
  expanded?: boolean;
  onToggle?: () => void;
  onOpen: () => void;
  onAdd?: () => void;
  addTitle?: string;
}) {
  return (
    <div
      className={cn(
        'group flex w-full items-center gap-1 rounded-md px-1 py-1 text-xs transition-colors hover:bg-workspace-accent-10',
        active ? 'text-workspace-accent' : 'text-foreground'
      )}
    >
      {expandable ? (
        <button
          onClick={onToggle}
          className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded hover:bg-muted"
          title={expanded ? 'Collapse' : 'Expand'}
        >
          <ChevronRight size={10} className={cn('transition-transform', expanded && 'rotate-90')} />
        </button>
      ) : (
        <span className="h-4 w-4 flex-shrink-0" />
      )}
      <button onClick={onOpen} className="flex flex-1 items-center gap-2 truncate text-left">
        {icon}
        <span className={cn('flex-1 truncate', active && 'font-medium')}>{label}</span>
      </button>
      {onAdd && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onAdd();
          }}
          className="flex-shrink-0 rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
          title={addTitle}
        >
          <Plus size={12} />
        </button>
      )}
    </div>
  );
}

const GraphItemRow = React.memo(function GraphItemRow({
  graph,
  isSelected,
  onClick,
  onClear,
  onDelete,
}: {
  graph: GraphItem;
  isSelected: boolean;
  onClick: () => void;
  onClear?: () => void;
  onDelete?: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const showActions = !isSchemaGraph(graph) && (onClear != null || onDelete != null);

  return (
    <div className="relative">
      <div
        className={cn(
          'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors cursor-pointer hover:bg-workspace-accent-10',
          isSelected ? 'bg-workspace-accent-10 text-workspace-accent' : 'text-foreground'
        )}
        onClick={onClick}
      >
        {graph.type === 'workspace' ? <Database size={12} /> : <User size={12} />}
        <span className="flex-1 truncate">{graph.name}</span>
        {showActions && (
          <span
            className="rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
            onClick={(e) => {
              e.stopPropagation();
              setShowMenu((prev) => !prev);
            }}
          >
            <MoreVertical size={12} />
          </span>
        )}
      </div>

      {showMenu && showActions && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-32 rounded-md border border-border bg-popover p-1 shadow-lg">
            {onClear && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onClear();
                  setShowMenu(false);
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
              >
                <Eraser size={12} />
                Clear
              </button>
            )}
            {onDelete && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                  setShowMenu(false);
                }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-destructive hover:bg-destructive/10"
              >
                <Trash2 size={12} />
                Delete
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
});

const ViewRow = React.memo(function ViewRow({
  name,
  isActive,
  onClick,
  onDelete,
}: {
  name: string;
  isActive: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="relative">
      <div
        className={cn(
          'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors cursor-pointer hover:bg-workspace-accent-10',
          isActive ? 'bg-workspace-accent-10 text-workspace-accent' : 'text-foreground'
        )}
        onClick={onClick}
      >
        <Bookmark size={12} />
        <span className="flex-1 truncate">{name}</span>
        <span
          className="rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            setShowMenu((prev) => !prev);
          }}
        >
          <MoreVertical size={12} />
        </span>
      </div>

      {showMenu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-32 rounded-md border border-border bg-popover p-1 shadow-lg">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
                setShowMenu(false);
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs text-destructive hover:bg-destructive/10"
            >
              <Trash2 size={12} />
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
});

export function KnowledgeGraphSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const GRAPH_CACHE_REFRESH_EVENT = 'graph-cache-refresh';
  const router = useRouter();
  const { confirm, dialog: confirmDialog } = useConfirm();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { currentWorkspaceId } = useWorkspaceStore();
  const {
    selectedGraphId,
    visibleGraphIds,
    views,
    activeSavedViewId,
    selectGraph,
    setVisibleGraphs,
    setActiveSavedView,
    setViews,
  } = useKnowledgeGraphStore();

  const [availableGraphPacks, setAvailableGraphPacks] = useState<GraphPackItem[]>([]);
  const [networkExpanded, setNetworkExpanded] = useState(true);
  const [composerExpanded, setComposerExpanded] = useState(true);
  const [composerViews, setComposerViews] = useState<SavedView[]>([]);
  const availableGraphs = useMemo(
    () => availableGraphPacks.flatMap((pack) => pack.graphs),
    [availableGraphPacks]
  );
  const composerViewGroups = useMemo(() => groupViewsByFolder(composerViews), [composerViews]);

  const graphNetworkPath = getWorkspacePath(currentWorkspaceId, '/graph/network');
  const graphIndividualsPath = getWorkspacePath(currentWorkspaceId, '/graph/individuals');
  const graphComposerPath = getWorkspacePath(currentWorkspaceId, '/graph/explore-next');
  const graphCreateGraphPath = getWorkspacePath(currentWorkspaceId, '/graph/create-graph');
  const graphCreateIndividualPath = getWorkspacePath(currentWorkspaceId, '/graph/create-individual');
  const graphImportPath = getWorkspacePath(currentWorkspaceId, '/graph/import');
  const graphExportPath = getWorkspacePath(currentWorkspaceId, '/graph/export');

  const isNetworkRoute = pathname.startsWith(graphNetworkPath);
  const isIndividualsRoute = pathname.startsWith(graphIndividualsPath);
  const isComposerRoute = pathname.startsWith(graphComposerPath);
  const activeComposerViewId = searchParams.get('view_id');

  useEffect(() => {
    if (!currentWorkspaceId) return;
    router.prefetch(graphNetworkPath);
  }, [currentWorkspaceId, graphNetworkPath, router]);

  const fetchGraphs = useCallback(async (options?: { force?: boolean }) => {
    if (!currentWorkspaceId) return;
    try {
      const apiUrl = getApiUrl();
      let graphPacks: GraphPackItem[] = [];
      const listParams = new URLSearchParams({
        workspace_id: currentWorkspaceId,
      });
      if (options?.force) {
        // Avoid stale list after destructive mutations.
        listParams.set('_ts', Date.now().toString());
      }
      const namesRes = await authFetch(
        `${apiUrl}/api/graph/list?${listParams.toString()}`
      );
      if (namesRes.ok) {
        const namesData = await namesRes.json();
        const parsed = Array.isArray(namesData) ? namesData : [];
        const isPackedResponse = parsed.every(isGraphPackApiItem);
        const dedupeByName = (items: GraphItem[]): GraphItem[] => {
          const seen = new Set<string>();
          return items.filter((item) => {
            if (seen.has(item.name)) return false;
            seen.add(item.name);
            return true;
          });
        };
        if (isPackedResponse) {
          graphPacks = parsed
            .map((pack) => {
              const graphs = dedupeByName(
                pack.graphs
                  .filter(isGraphApiItem)
                  .map((g) => ({
                    id: g.id,
                    name: g.label ?? g.id,
                    type: 'workspace' as const,
                    uri: g.uri,
                  }))
                  .sort((a, b) => a.name.localeCompare(b.name))
              );
              return {
                roleLabel: (pack.role_label ?? 'unknown').toString(),
                graphs,
              };
            })
            .filter((pack) => pack.graphs.length > 0)
            .sort((a, b) => a.roleLabel.localeCompare(b.roleLabel));
        } else {
          const graphs = dedupeByName(
            parsed
              .filter(isGraphApiItem)
              .map((g) => ({
                id: g.id,
                name: g.label ?? g.id,
                type: 'workspace' as const,
                uri: g.uri,
              }))
              .sort((a, b) => a.name.localeCompare(b.name))
          );
          graphPacks = graphs.length > 0 ? [{ roleLabel: 'unknown', graphs }] : [];
        }
      }

      const graphs = graphPacks.flatMap((pack) => pack.graphs);

      setAvailableGraphPacks(graphPacks);

      // Sanitize visible graphs: drop stale IDs from other workspaces
      const allowedIds = graphs.map((g) => g.id);
      const filteredVisible = visibleGraphIds.filter((id) => allowedIds.includes(id));

      if (filteredVisible.length === 0) {
        // Default to both layers (overlay) when nothing selected
        const defaults = graphs.map((g) => g.id);
        if (defaults.length > 0) setVisibleGraphs(defaults);
      } else if (filteredVisible.length !== visibleGraphIds.length) {
        setVisibleGraphs(filteredVisible);
      }

      if (!selectedGraphId || !allowedIds.includes(selectedGraphId)) {
        const firstId = graphs[0]?.id ?? null;
        selectGraph(firstId);
        // Navigate to entities view when auto-selecting for the first time.
        if (firstId && !selectedGraphId) {
          setVisibleGraphs([firstId]);
          router.push(getWorkspacePath(currentWorkspaceId, '/graph?view=entities'));
        }
      }
    } catch (err) {
      // Silently handle 403 (permission denied) - user doesn't have access to this workspace
      if (err instanceof Error && err.message.includes('403')) {
        return;
      }
      console.error('Failed to fetch graphs:', err);
    }
  }, [currentWorkspaceId, router, selectGraph, selectedGraphId, setVisibleGraphs, visibleGraphIds]);

  useEffect(() => {
    void fetchGraphs();
  }, [fetchGraphs]);

  useEffect(() => {
    const onGraphListUpdate = () => {
      void fetchGraphs({ force: true });
    };
    window.addEventListener('graph-list-update', onGraphListUpdate);
    return () => window.removeEventListener('graph-list-update', onGraphListUpdate);
  }, [fetchGraphs]);

  // Legacy graph-view store population (kept for the legacy /graph page + root navigation).
  const fetchViewsFromApi = useCallback(async (): Promise<GraphView[]> => {
    if (!currentWorkspaceId) return [];
    try {
      const apiUrl = getApiUrl();
      const response = await authFetch(
        `${apiUrl}/api/view/list?workspace_id=${encodeURIComponent(currentWorkspaceId)}`
      );
      if (!response.ok) return [];
      const data = await response.json();
      const normalizedViews: GraphView[] = Array.isArray(data)
        ? data.map((item: {
          id: string;
          label?: string;
          user_id?: string | null;
          scope?: 'workspace' | 'user';
          name?: string;
          graph_names?: string[];
          graph_filters?: string[];
          created_at?: string;
        }) => ({
          id: item.id,
          name: item.label ?? item.name ?? item.id,
          scope: item.scope === 'workspace' ? 'workspace' : 'user',
          userId: item.user_id ?? undefined,
          type: 'entities',
          graphIds: Array.isArray(item.graph_names) ? item.graph_names : [],
          filters: [],
          createdAt: item.created_at ? new Date(item.created_at) : new Date(),
        }))
        : [];
      setViews(normalizedViews);
      return normalizedViews;
    } catch (error) {
      console.error('Failed to fetch graph views:', error);
      return [];
    }
  }, [currentWorkspaceId, setViews]);

  useEffect(() => {
    void fetchViewsFromApi();
  }, [fetchViewsFromApi]);

  // Composer (query) views — the Composer submenu. Fetched via the graph-query client (kind=query)
  // and kept in sync with the Composer page via the 'views-changed' window event.
  const refreshComposerViews = useCallback(() => {
    if (!currentWorkspaceId) {
      setComposerViews([]);
      return;
    }
    listViews({ workspaceId: currentWorkspaceId, path: '', recursive: true })
      .then((vs) => setComposerViews(vs.filter((v) => v.kind === 'query')))
      .catch(() => setComposerViews([]));
  }, [currentWorkspaceId]);

  useEffect(() => {
    refreshComposerViews();
  }, [refreshComposerViews]);

  useEffect(() => {
    const onChanged = () => refreshComposerViews();
    window.addEventListener('views-changed', onChanged);
    return () => window.removeEventListener('views-changed', onChanged);
  }, [refreshComposerViews]);

  const handleDeleteView = useCallback(
    async (view: SavedView) => {
      const workspaceId = currentWorkspaceId;
      if (!workspaceId) return;
      const shouldDelete = await confirm({
        title: `Delete view "${view.name ?? view.label}"?`,
        description: 'This removes the saved view and its query. This action cannot be undone.',
        confirmLabel: 'Delete View',
        destructive: true,
      });
      if (!shouldDelete) return;
      try {
        await deleteView(workspaceId, view.id);
        refreshComposerViews();
        window.dispatchEvent(new CustomEvent('views-changed'));
      } catch (err) {
        console.error('Failed to delete view:', err);
      }
    },
    [confirm, currentWorkspaceId, refreshComposerViews]
  );

  const selectKnowledgeGraphRoot = () => {
    if (activeSavedViewId) {
      const activeView = views.find((view) => view.id === activeSavedViewId);
      if (activeView?.graphIds && activeView.graphIds.length > 0) {
        setVisibleGraphs(activeView.graphIds);
      }
      return;
    }

    if (selectedGraphId && availableGraphs.some((graph) => graph.id === selectedGraphId)) {
      setVisibleGraphs([selectedGraphId]);
      return;
    }

    const firstGraphId = availableGraphs[0]?.id;
    if (firstGraphId) {
      setActiveSavedView(null);
      selectGraph(firstGraphId);
      setVisibleGraphs([firstGraphId]);
    }
  };

  const clearGraphHandler = (graph: GraphItem) => async () => {
    const shouldClear = await confirm({
      title: `Clear graph "${graph.name}"?`,
      description:
        'This will remove all triples from this graph. The graph itself will remain. This action cannot be undone.',
      confirmLabel: 'Clear Graph',
      destructive: true,
    });
    if (!shouldClear) return;
    try {
      const apiUrl = getApiUrl();
      const response = await authFetch(`${apiUrl}/api/graph/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: currentWorkspaceId, uri: graph.uri }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const message = typeof err?.detail === 'string' ? err.detail : 'Failed to clear graph';
        console.error('Failed to clear graph:', message, err);
        return;
      }
      setActiveSavedView(null);
      selectGraph(graph.id);
      setVisibleGraphs([graph.id]);
      router.push(graphNetworkPath);
      window.dispatchEvent(new CustomEvent(GRAPH_CACHE_REFRESH_EVENT));
    } catch (err) {
      console.error('Failed to clear graph:', err);
    }
  };

  const deleteGraphHandler = (graph: GraphItem) => async () => {
    const shouldDelete = await confirm({
      title: `Delete graph "${graph.name}"?`,
      description: 'This will remove the graph and all its triples. This action cannot be undone.',
      confirmLabel: 'Delete Graph',
      destructive: true,
    });
    if (!shouldDelete) return;
    try {
      const apiUrl = getApiUrl();
      const response = await authFetch(`${apiUrl}/api/graph/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: currentWorkspaceId, uri: graph.uri }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const message = typeof err?.detail === 'string' ? err.detail : 'Failed to delete graph';
        console.error('Failed to delete graph:', message, err);
        return;
      }
      // Force immediate UI refresh of graph list, then reconcile with backend.
      let remainingGraphsSnapshot: GraphItem[] = [];
      setAvailableGraphPacks((prev) => {
        const nextPacks = prev
          .map((currentPack) => ({
            ...currentPack,
            graphs: currentPack.graphs.filter((item) => item.id !== graph.id),
          }))
          .filter((currentPack) => currentPack.graphs.length > 0);
        remainingGraphsSnapshot = nextPacks.flatMap((currentPack) => currentPack.graphs);
        return nextPacks;
      });
      window.dispatchEvent(new CustomEvent(GRAPH_CACHE_REFRESH_EVENT));
      window.dispatchEvent(new CustomEvent('graph-list-update'));
      await fetchGraphs({ force: true });
      if (selectedGraphId === graph.id) {
        const nextGraphId = remainingGraphsSnapshot[0]?.id ?? null;
        setActiveSavedView(null);
        selectGraph(nextGraphId);
        setVisibleGraphs(nextGraphId ? [nextGraphId] : []);
        router.push(graphNetworkPath);
      }
    } catch (err) {
      console.error('Failed to delete graph:', err);
    }
  };

  return (
    <CollapsibleSection
      id="graph"
      icon={<Waypoints size={18} />}
      label="Knowledge Graph"
      description="Visualize and explore your knowledge"
      href={graphNetworkPath}
      collapsed={collapsed}
      detailOnly={detailOnly}
      onNavigate={selectKnowledgeGraphRoot}
    >
      {/* Quick actions — create / import / export */}
      <div className="flex items-center gap-1 px-1 pb-1">
        {[
          { icon: <Network size={14} />, label: 'Create graph', onClick: () => router.push(graphCreateGraphPath) },
          { icon: <Users size={14} />, label: 'Create individual', onClick: () => router.push(graphCreateIndividualPath) },
          { icon: <Upload size={14} />, label: 'Import triples', onClick: () => router.push(graphImportPath) },
          { icon: <Download size={14} />, label: 'Export triples', onClick: () => router.push(graphExportPath) },
        ].map((action) => (
          <button
            key={action.label}
            type="button"
            onClick={action.onClick}
            title={action.label}
            aria-label={action.label}
            className="flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-workspace-accent-10 hover:text-workspace-accent"
          >
            {action.icon}
          </button>
        ))}
      </div>

      {/* Network — pick which graph(s) to view */}
      <div className={cn('px-1', networkExpanded && 'pb-1')}>
        <AppEntry
          icon={<Network size={14} />}
          label="Network"
          active={isNetworkRoute}
          expandable
          expanded={networkExpanded}
          onToggle={() => setNetworkExpanded((prev) => !prev)}
          onOpen={() => {
            setActiveSavedView(null);
            router.push(graphNetworkPath);
          }}
          onAdd={() => {
            setActiveSavedView(null);
            router.push(graphCreateGraphPath);
          }}
          addTitle="New graph"
        />
        {networkExpanded && (
          <div className="ml-3 space-y-0.5 border-l border-border/50 pl-1">
            {availableGraphs.length === 0 ? (
              <p className="px-2 py-1 text-xs text-muted-foreground">No named graphs</p>
            ) : (
              availableGraphPacks.map((pack, packIndex) => (
                <React.Fragment key={pack.roleLabel}>
                  {packIndex > 0 && <div className="my-1 h-px bg-border/50" />}
                  {pack.graphs.map((graph) => (
                    <GraphItemRow
                      key={graph.id}
                      graph={graph}
                      isSelected={isNetworkRoute && selectedGraphId === graph.id}
                      onClick={() => {
                        setActiveSavedView(null);
                        selectGraph(graph.id);
                        setVisibleGraphs([graph.id]);
                        router.push(graphNetworkPath);
                      }}
                      onClear={isSchemaGraph(graph) ? undefined : clearGraphHandler(graph)}
                      onDelete={isSchemaGraph(graph) ? undefined : deleteGraphHandler(graph)}
                    />
                  ))}
                </React.Fragment>
              ))
            )}
          </div>
        )}
      </div>

      {/* Composer — saved views */}
      <div className={cn('px-1', composerExpanded && 'pb-2')}>
        <AppEntry
          icon={<Table2 size={14} />}
          label="Composer"
          active={isComposerRoute}
          expandable
          expanded={composerExpanded}
          onToggle={() => setComposerExpanded((prev) => !prev)}
          onOpen={() => router.push(graphComposerPath)}
        />
        {composerExpanded && (
          <div className="ml-3 space-y-0.5 border-l border-border/50 pl-1">
            <div className="px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Views
            </div>
            {composerViews.length === 0 ? (
              <p className="px-2 py-1 text-xs text-muted-foreground">No saved views</p>
            ) : (
              composerViewGroups.map((group) => (
                <div key={group.path || '(root)'} className="space-y-0.5">
                  {group.path && (
                    <div className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/70">
                      <Folder size={10} className="flex-shrink-0" />
                      <span className="truncate" title={group.path}>{group.path}</span>
                    </div>
                  )}
                  {group.views.map((view) => (
                    <ViewRow
                      key={view.id}
                      name={view.name ?? view.label}
                      isActive={isComposerRoute && activeComposerViewId === view.id}
                      onClick={() =>
                        router.push(`${graphComposerPath}?view_id=${encodeURIComponent(view.id)}`)
                      }
                      onDelete={() => handleDeleteView(view)}
                    />
                  ))}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Individuals — its own page selects graphs, so no submenu (kept last) */}
      <div className="px-1">
        <AppEntry
          icon={<Users size={14} />}
          label="Individuals"
          active={isIndividualsRoute}
          expandable={false}
          onOpen={() => {
            setActiveSavedView(null);
            router.push(graphIndividualsPath);
          }}
          onAdd={() => router.push(graphCreateIndividualPath)}
          addTitle="New individual"
        />
      </div>

      {confirmDialog}
    </CollapsibleSection>
  );
}
