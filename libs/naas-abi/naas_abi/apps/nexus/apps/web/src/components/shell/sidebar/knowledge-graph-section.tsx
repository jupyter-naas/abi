'use client';

import React, { useState, useEffect } from 'react';
import {
  Waypoints, Plus, Filter, MoreVertical, Edit2, Trash2, Eraser,
  RefreshCw, Database, User, UserPlus, ChevronRight, Code,
} from 'lucide-react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useKnowledgeGraphStore, type GraphView } from '@/stores/knowledge-graph';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

interface GraphItem {
  id: string;
  name: string;
  type: 'workspace' | 'user';
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
          'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors cursor-pointer',
          isSelected && 'bg-workspace-accent-10 text-workspace-accent',
          'hover:bg-workspace-accent-10 text-foreground'
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

const ViewItemRow = React.memo(function ViewItemRow({
  name,
  isActive,
  onSelect,
  onEdit,
  onDelete,
}: {
  name: string;
  isActive: boolean;
  onSelect: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={onSelect}
        className={cn(
          'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors hover:bg-workspace-accent-10',
          isActive ? 'bg-workspace-accent-10 text-workspace-accent' : 'text-muted-foreground'
        )}
      >
        <Filter size={12} />
        <span className="flex-1 truncate">{name}</span>
        <span
          className="rounded p-0.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100"
          onClick={(event) => {
            event.stopPropagation();
            setShowMenu((prev) => !prev);
          }}
        >
          <MoreVertical size={12} />
        </span>
      </button>

      {showMenu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-32 rounded-md border border-border bg-popover p-1 shadow-lg">
            <button
              onClick={(event) => {
                event.stopPropagation();
                onEdit();
                setShowMenu(false);
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
            >
              <Edit2 size={12} />
              Edit
            </button>
            <button
              onClick={(event) => {
                event.stopPropagation();
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

export function KnowledgeGraphSection({ collapsed }: { collapsed: boolean }) {
  const GRAPH_CACHE_REFRESH_EVENT = 'graph-cache-refresh';
  const router = useRouter();
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
    deleteView,
    setViews,
  } = useKnowledgeGraphStore();

  const [availableGraphs, setAvailableGraphs] = useState<GraphItem[]>([]);
  const [graphsExpanded, setGraphsExpanded] = useState(true);
  const [viewsExpanded, setViewsExpanded] = useState(true);
  const graphPath = getWorkspacePath(currentWorkspaceId, '/graph');
  const isGraphRoute = pathname.startsWith(graphPath);
  const requestedView = searchParams.get('view');
  const isCreateIndividualView = requestedView === 'create-individual';
  const isSparqlView = requestedView === 'sparql';
  const showGraphRowSelection = isGraphRoute && !isCreateIndividualView && !isSparqlView;

  useEffect(() => {
    if (!currentWorkspaceId) return;
    router.prefetch(graphPath);
  }, [currentWorkspaceId, graphPath, router]);

  const fetchGraphs = async () => {
    if (!currentWorkspaceId) return;
    try {
      const apiUrl = getApiUrl();
      let graphList: { id: string; label: string }[] = [];
      const namesRes = await authFetch(
        `${apiUrl}/api/graph/list?workspace_id=${encodeURIComponent(currentWorkspaceId)}`
      );
      if (namesRes.ok) {
        const namesData = await namesRes.json();
        const parsed = Array.isArray(namesData) ? namesData : [];
        const normalized = parsed
          .filter((g: unknown) => g && typeof g === 'object' && 'id' in g && typeof (g as { id: unknown }).id === 'string')
          .map((g: { id: string; label?: string }) => ({ id: g.id, label: g.label ?? g.id }));
        graphList = normalized;
      }

      const graphs: GraphItem[] = graphList.map((graph) => ({
        id: graph.id,
        name: graph.label,
        type: 'workspace' as const,
      }));

      setAvailableGraphs(graphs);

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
        selectGraph(graphs[0]?.id ?? null);
      }
    } catch (err) {
      // Silently handle 403 (permission denied) - user doesn't have access to this workspace
      if (err instanceof Error && err.message.includes('403')) {
        return;
      }
      console.error('Failed to fetch graphs:', err);
    }
  };

  useEffect(() => {
    fetchGraphs();
  }, [currentWorkspaceId, setVisibleGraphs]);

  useEffect(() => {
    const onGraphListUpdate = () => {
      void fetchGraphs();
    };
    window.addEventListener('graph-list-update', onGraphListUpdate);
    return () => window.removeEventListener('graph-list-update', onGraphListUpdate);
  }, [currentWorkspaceId]);

  useEffect(() => {
    const fetchViews = async () => {
      if (!currentWorkspaceId) return;
      try {
        const apiUrl = getApiUrl();
        const response = await authFetch(
          `${apiUrl}/api/view/list?workspace_id=${encodeURIComponent(currentWorkspaceId)}`
        );
        if (!response.ok) return;
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
      } catch (error) {
        console.error('Failed to fetch graph views:', error);
      }
    };
    fetchViews();
  }, [currentWorkspaceId, setViews]);

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

  return (
    <CollapsibleSection
      id="graph"
      icon={<Waypoints size={18} />}
      label="Knowledge Graph"
      description="Visualize and explore your knowledge"
      href={graphPath}
      collapsed={collapsed}
      onNavigate={selectKnowledgeGraphRoot}
    >
      <div className="flex items-center gap-0.5 px-1 pb-1">
        <button
          onClick={() => router.push(getWorkspacePath(currentWorkspaceId, '/graph?view=create-individual'))}
          className={cn(
            'flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
            isGraphRoute && isCreateIndividualView && 'bg-workspace-accent-10 text-workspace-accent'
          )}
          title="New Individual"
        >
          <UserPlus size={14} />
        </button>
        <button
          onClick={() => {
            setActiveSavedView(null);
            window.dispatchEvent(new CustomEvent(GRAPH_CACHE_REFRESH_EVENT));
            router.push(getWorkspacePath(currentWorkspaceId, '/graph'));
          }}
          className={cn(
            'flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
            showGraphRowSelection && !selectedGraphId && 'bg-workspace-accent-10 text-workspace-accent'
          )}
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
        <button
          onClick={() => router.push(getWorkspacePath(currentWorkspaceId, '/graph?view=sparql'))}
          className={cn(
            'flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
            isGraphRoute && isSparqlView && 'bg-workspace-accent-10 text-workspace-accent'
          )}
          title="SPARQL"
        >
          <Code size={14} />
        </button>
      </div>

      <div className={cn('px-1', graphsExpanded && 'pb-2')}>
        <button
          onClick={() => setGraphsExpanded((prev) => !prev)}
          className={cn(
            'flex w-full items-center gap-1 rounded-md px-1 py-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:bg-workspace-accent-10',
            graphsExpanded && 'mb-1'
          )}
        >
          <ChevronRight
            size={10}
            className={cn('flex-shrink-0 transition-transform', graphsExpanded && 'rotate-90')}
          />
          <span className="flex-1 text-left">Graphs ({availableGraphs.length})</span>
          <span
            onClick={(e) => {
              e.stopPropagation();
              setActiveSavedView(null);
              router.push(getWorkspacePath(currentWorkspaceId, '/graph?view=create-graph'));
            }}
            className="rounded p-0.5 hover:bg-muted"
            title="New Graph"
          >
            <Plus size={12} />
          </span>
        </button>
        {graphsExpanded && (
          <div className="space-y-0.5">
            {availableGraphs.length === 0 ? (
              <p className="px-2 py-1 text-xs text-muted-foreground">No named graphs</p>
            ) : (
              availableGraphs.map((graph) => (
                <GraphItemRow
                  key={graph.id}
                  graph={graph}
                  isSelected={showGraphRowSelection && selectedGraphId === graph.id}
                  onClick={() => {
                    setActiveSavedView(null);
                    selectGraph(graph.id);
                    setVisibleGraphs([graph.id]);
                    router.push(getWorkspacePath(currentWorkspaceId, '/graph'));
                  }}
                  onClear={
                    isSchemaGraph(graph)
                      ? undefined
                      : () => {
                          if (!confirm(`Clear all triples in graph "${graph.name}"? This cannot be undone.`)) return;
                          const run = async () => {
                            try {
                              const apiUrl = getApiUrl();
                              const response = await authFetch(`${apiUrl}/api/graph/clear`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  workspace_id: currentWorkspaceId,
                                  graph_uri: graph.id,
                                }),
                              });
                              if (!response.ok) {
                                const err = await response.json().catch(() => ({}));
                                alert(err.detail || 'Failed to clear graph');
                                return;
                              }
                              window.dispatchEvent(new CustomEvent(GRAPH_CACHE_REFRESH_EVENT));
                            } catch (err) {
                              console.error('Failed to clear graph:', err);
                              alert('Failed to clear graph');
                            }
                          };
                          void run();
                        }
                  }
                  onDelete={
                    isSchemaGraph(graph)
                      ? undefined
                      : () => {
                          if (!confirm(`Delete graph "${graph.name}"? This cannot be undone.`)) return;
                          const run = async () => {
                            try {
                              const apiUrl = getApiUrl();
                              const response = await authFetch(`${apiUrl}/api/graph/delete`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  workspace_id: currentWorkspaceId,
                                  graph_uri: graph.id,
                                }),
                              });
                              if (!response.ok) {
                                const err = await response.json().catch(() => ({}));
                                alert(err.detail || 'Failed to delete graph');
                                return;
                              }
                              window.dispatchEvent(new CustomEvent(GRAPH_CACHE_REFRESH_EVENT));
                              window.dispatchEvent(new CustomEvent('graph-list-update'));
                              await fetchGraphs();
                            } catch (err) {
                              console.error('Failed to delete graph:', err);
                              alert('Failed to delete graph');
                            }
                          };
                          void run();
                        }
                  }
                />
              ))
            )}
          </div>
        )}
      </div>

      <div className={cn('px-1', viewsExpanded && 'pb-2')}>
        <button
          onClick={() => setViewsExpanded((prev) => !prev)}
          className={cn(
            'flex w-full items-center gap-1 rounded-md px-1 py-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:bg-workspace-accent-10',
            viewsExpanded && 'mb-1'
          )}
        >
          <ChevronRight
            size={10}
            className={cn('flex-shrink-0 transition-transform', viewsExpanded && 'rotate-90')}
          />
          <span className="flex-1 text-left">Views ({views.length})</span>
          <span
            onClick={(event) => {
              event.stopPropagation();
              selectGraph(null);
              router.push(getWorkspacePath(currentWorkspaceId, '/graph?view=new-view'));
            }}
            className="rounded p-0.5 hover:bg-muted"
            title="New View"
          >
            <Plus size={12} />
          </span>
        </button>
        {viewsExpanded && (
          <div className="space-y-0.5">
            {views.length === 0 ? (
              <p className="px-2 py-1 text-xs text-muted-foreground">No saved views</p>
            ) : (
              views.map((view) => (
                <ViewItemRow
                  key={view.id}
                  name={view.name}
                  isActive={activeSavedViewId === view.id}
                  onEdit={() => {
                    selectGraph(null);
                    setActiveSavedView(view.id);
                    router.push(
                      getWorkspacePath(
                        currentWorkspaceId,
                        `/graph?view=edit-view&view_id=${encodeURIComponent(view.id)}`
                      )
                    );
                  }}
                  onDelete={() => {
                    const workspaceId = currentWorkspaceId;
                    if (!workspaceId) return;
                    if (confirm(`Delete view "${view.name}"?`)) {
                      const run = async () => {
                        try {
                          const apiUrl = getApiUrl();
                          const response = await authFetch(
                            `${apiUrl}/api/view/${encodeURIComponent(view.id)}?workspace_id=${encodeURIComponent(workspaceId)}`,
                            { method: 'DELETE' }
                          );
                          if (!response.ok) return;
                          deleteView(view.id);
                        } catch (error) {
                          console.error('Failed to delete view:', error);
                        }
                      };
                      void run();
                    }
                  }}
                  onSelect={() => {
                    selectGraph(null);
                    setActiveSavedView(view.id);
                    if (view.graphIds && view.graphIds.length > 0) {
                      setVisibleGraphs(view.graphIds);
                    }
                    router.push(getWorkspacePath(currentWorkspaceId, '/graph'));
                  }}
                />
              ))
            )}
          </div>
        )}
      </div>

    </CollapsibleSection>
  );
}
