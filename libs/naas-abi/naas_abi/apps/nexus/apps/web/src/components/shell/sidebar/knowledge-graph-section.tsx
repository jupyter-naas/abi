'use client';

import React, { useState, useEffect } from 'react';
import {
  Waypoints, Plus, Filter, MoreVertical, Edit2, Trash2,
  RefreshCw, Eye, EyeOff, Database, User, UserPlus, ChevronRight, Code,
} from 'lucide-react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
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
  onRename,
  onDelete,
  isRenaming,
  onStartRename,
  onCancelRename,
}: {
  name: string;
  isActive: boolean;
  onSelect: () => void;
  onRename: (newName: string) => void;
  onDelete: () => void;
  isRenaming: boolean;
  onStartRename: () => void;
  onCancelRename: () => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const [editValue, setEditValue] = useState(name);

  const handleRenameSubmit = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== name) {
      onRename(trimmed);
    }
    onCancelRename();
  };

  if (isRenaming) {
    return (
      <div className="flex items-center gap-2 rounded-md px-2 py-1 text-xs">
        <Filter size={12} className="flex-shrink-0 text-muted-foreground" />
        <input
          type="text"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleRenameSubmit();
            } else if (e.key === 'Escape') {
              onCancelRename();
            }
          }}
          onBlur={handleRenameSubmit}
          autoFocus
          className="flex-1 border-b border-workspace-accent bg-transparent text-xs outline-none"
        />
      </div>
    );
  }

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
                onStartRename();
                setShowMenu(false);
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
            >
              <Edit2 size={12} />
              Rename
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
    updateSavedView,
    deleteView,
  } = useKnowledgeGraphStore();

  const [availableGraphs, setAvailableGraphs] = useState<GraphItem[]>([]);
  const [graphsExpanded, setGraphsExpanded] = useState(true);
  const [viewsExpanded, setViewsExpanded] = useState(true);
  const [renamingViewId, setRenamingViewId] = useState<string | null>(null);
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
      let graphNames: string[] = ['default'];
      const namesRes = await authFetch(`${apiUrl}/api/graph/names`);
      if (namesRes.ok) {
        const namesData = await namesRes.json();
        const parsed = Array.isArray(namesData?.graph_names) ? namesData.graph_names : [];
        const normalized = parsed.filter((name): name is string => typeof name === 'string' && name.length > 0);
        if (normalized.length > 0) graphNames = normalized;
      }

      const graphs: GraphItem[] = await Promise.all(
        graphNames.map(async (graphName) => {
          let nodeCount = 0;
          const wsRes = await authFetch(
            `${apiUrl}/api/graph/network/${encodeURIComponent(graphName)}?workspace_id=${encodeURIComponent(currentWorkspaceId)}`
          );
          if (wsRes.ok) {
            const wsData = await wsRes.json();
            const uniqueNodes = Array.isArray(wsData?.nodes)
              ? Array.from(new Map(wsData.nodes.map((node: { id: string }) => [node.id, node])).values())
              : [];
            nodeCount = uniqueNodes.length;
          }
          return {
            id: graphName,
            name: graphName,
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

  return (
    <CollapsibleSection
      id="graph"
      icon={<Waypoints size={18} />}
      label="Knowledge Graph"
      description="Visualize and explore your knowledge"
      href={graphPath}
      collapsed={collapsed}
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
          onClick={() => router.push(getWorkspacePath(currentWorkspaceId, '/graph'))}
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
                  isRenaming={renamingViewId === view.id}
                  onStartRename={() => setRenamingViewId(view.id)}
                  onCancelRename={() => setRenamingViewId(null)}
                  onRename={(newName) => updateSavedView(view.id, { name: newName })}
                  onDelete={() => {
                    if (confirm(`Delete view "${view.name}"?`)) {
                      deleteView(view.id);
                    }
                  }}
                  onSelect={() => {
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
