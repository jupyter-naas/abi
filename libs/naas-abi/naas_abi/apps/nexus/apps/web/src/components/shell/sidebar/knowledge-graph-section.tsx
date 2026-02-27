'use client';

import React, { useState, useEffect } from 'react';
import {
  Waypoints, Plus, Filter, MoreVertical, Edit2, Trash2,
  RefreshCw, Eye, EyeOff, Database, User, UserPlus, ChevronRight, Code,
} from 'lucide-react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useKnowledgeGraphStore, type GraphTripleFilter, type GraphView } from '@/stores/knowledge-graph';
import { authFetch } from '@/stores/auth';
import { getApiUrl } from '@/lib/config';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

interface GraphItem {
  id: string;
  name: string;
  type: 'workspace' | 'user';
  nodeCount: number;
}

const GraphItemRow = React.memo(function GraphItemRow({
  graph,
  isVisible,
  isSelected,
  onToggle,
  onClick,
}: {
  graph: GraphItem;
  isVisible: boolean;
  isSelected: boolean;
  onToggle: () => void;
  onClick: () => void;
}) {
  return (
    <div
      className={cn(
        'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors cursor-pointer',
        isVisible ? 'text-foreground' : 'text-muted-foreground',
        isSelected && 'bg-workspace-accent-10 text-workspace-accent',
        'hover:bg-workspace-accent-10'
      )}
      onClick={onClick}
    >
      {graph.type === 'workspace' ? <Database size={12} /> : <User size={12} />}
      <span className="flex-1 truncate">{graph.name}</span>
      <span className="text-[10px] text-muted-foreground">{graph.nodeCount}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggle();
        }}
        className="flex h-5 w-5 items-center justify-center rounded text-muted-foreground opacity-0 transition-opacity hover:bg-muted/50 group-hover:opacity-100"
        title={isVisible ? 'Hide graph' : 'Show graph'}
      >
        {isVisible ? (
          <Eye size={12} className="text-workspace-accent" />
        ) : (
          <EyeOff size={12} />
        )}
      </button>
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
    toggleGraphVisibility,
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

  const fetchGraphs = async () => {
    if (!currentWorkspaceId) return;
    try {
      const apiUrl = getApiUrl();
      let graphList: { id: string; label: string }[] = [{ id: 'default', label: 'default' }];
      const namesRes = await authFetch(`${apiUrl}/api/graph/names`);
      if (namesRes.ok) {
        const namesData = await namesRes.json();
        const parsed = Array.isArray(namesData?.graphs) ? namesData.graphs : [];
        const normalized = parsed
          .filter((g: unknown) => g && typeof g === 'object' && 'id' in g && typeof (g as { id: unknown }).id === 'string')
          .map((g: { id: string; label?: string }) => ({ id: g.id, label: g.label ?? g.id }));
        if (normalized.length > 0) graphList = normalized;
      }

      const graphs: GraphItem[] = await Promise.all(
        graphList.map(async (graph) => {
          let nodeCount = 0;
          const wsRes = await authFetch(
            `${apiUrl}/api/graph/network?workspace_id=${encodeURIComponent(currentWorkspaceId)}&graph_id=${encodeURIComponent(graph.id)}`
          );
          if (wsRes.ok) {
            const wsData = await wsRes.json();
            const uniqueNodes = Array.isArray(wsData?.nodes)
              ? Array.from(new Map(wsData.nodes.map((node: { id: string }) => [node.id, node])).values())
              : [];
            nodeCount = uniqueNodes.length;
          }
          return {
            id: graph.id,
            name: graph.label,
            type: 'workspace' as const,
            nodeCount,
          };
        })
      );

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
  }, [currentWorkspaceId, visibleGraphIds.length, setVisibleGraphs]);

  useEffect(() => {
    const fetchViews = async () => {
      if (!currentWorkspaceId) return;
      try {
        const apiUrl = getApiUrl();
        const response = await authFetch(
          `${apiUrl}/api/graph/views?workspace_id=${encodeURIComponent(currentWorkspaceId)}`
        );
        if (!response.ok) return;
        const data = await response.json();
        const normalizedViews: GraphView[] = Array.isArray(data)
          ? data.map((item: {
            id: string;
            name: string;
            graph_names?: string[];
            filters?: GraphTripleFilter[];
            created_at?: string;
          }) => ({
            id: item.id,
            name: item.name,
            type: 'entities',
            graphIds: Array.isArray(item.graph_names) ? item.graph_names : [],
            filters: Array.isArray(item.filters) ? item.filters : [],
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

  return (
    <CollapsibleSection
      id="graph"
      icon={<Waypoints size={18} />}
      label="Knowledge Graph"
      description="Visualize and explore your knowledge"
      href={graphPath}
      collapsed={collapsed}
      onNavigate={() => setActiveSavedView(null)}
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

      {availableGraphs.length > 0 && (
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
            <span>Graphs ({availableGraphs.length})</span>
          </button>
          {graphsExpanded && (
            <div className="space-y-0.5">
              {availableGraphs.map((graph) => (
                <GraphItemRow
                  key={graph.id}
                  graph={graph}
                  isVisible={visibleGraphIds.includes(graph.id)}
                  isSelected={showGraphRowSelection && selectedGraphId === graph.id}
                  onToggle={() => toggleGraphVisibility(graph.id)}
                  onClick={() => {
                    setActiveSavedView(null);
                    selectGraph(graph.id);
                    if (!visibleGraphIds.includes(graph.id)) {
                      toggleGraphVisibility(graph.id);
                    }
                    router.push(getWorkspacePath(currentWorkspaceId, '/graph'));
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}

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
                    if (confirm(`Delete view "${view.name}"?`)) {
                      const run = async () => {
                        try {
                          const apiUrl = getApiUrl();
                          const response = await authFetch(
                            `${apiUrl}/api/graph/views/${encodeURIComponent(view.id)}?workspace_id=${encodeURIComponent(currentWorkspaceId)}`,
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
