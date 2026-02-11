'use client';

import React, { useState, useEffect } from 'react';
import {
  Waypoints, GitBranch, LayoutGrid, FileCode, Network, Box,
  RefreshCw, Eye, EyeOff, Database, User,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import { useKnowledgeGraphStore } from '@/stores/knowledge-graph';
import { authFetch, useAuthStore } from '@/stores/auth';
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
  onToggle,
  onClick,
}: {
  graph: GraphItem;
  isVisible: boolean;
  onToggle: () => void;
  onClick: () => void;
}) {
  return (
    <div
      className={cn(
        'group flex w-full items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors cursor-pointer',
        isVisible ? 'text-foreground' : 'text-muted-foreground',
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

export function KnowledgeGraphSection({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const { currentWorkspaceId } = useWorkspaceStore();
  const currentWorkspace = useWorkspaceStore((s) => s.workspaces.find((w) => w.id === s.currentWorkspaceId));
  const {
    activeViewType,
    setActiveViewType,
    visibleGraphIds,
    toggleGraphVisibility,
    setVisibleGraphs,
  } = useKnowledgeGraphStore();

  const [availableGraphs, setAvailableGraphs] = useState<GraphItem[]>([]);

  useEffect(() => {
    if (!currentWorkspaceId) return;

    const fetchGraphs = async () => {
      try {
        const apiUrl = getApiUrl();
        const graphs: GraphItem[] = [];

        const wsRes = await authFetch(`${apiUrl}/api/graph/workspaces/${currentWorkspaceId}`);
        if (wsRes.ok) {
          const wsData = await wsRes.json();
          // Only expose exactly two graphs per workspace: Persons and Organizations
          const personCount = wsData.nodes?.filter((n: any) => n.type === 'Person').length || 0;
          const orgCount = wsData.nodes?.filter((n: any) => n.type === 'Organization').length || 0;
          graphs.push({ id: `${currentWorkspaceId}#layer=person`, name: 'Persons', type: 'workspace', nodeCount: personCount });
          graphs.push({ id: `${currentWorkspaceId}#layer=organization`, name: 'Organizations', type: 'workspace', nodeCount: orgCount });
        }

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
      } catch (err) {
        // Silently handle 403 (permission denied) - user doesn't have access to this workspace
        if (err instanceof Error && err.message.includes('403')) {
          return;
        }
        console.error('Failed to fetch graphs:', err);
      }
    };

    fetchGraphs();
  }, [currentWorkspaceId, currentWorkspace?.name, visibleGraphIds.length, setVisibleGraphs]);

  const viewIcons: Record<string, React.ReactNode> = {
    visual: <GitBranch size={12} />,
    table: <LayoutGrid size={12} />,
    sparql: <FileCode size={12} />,
    schema: <Network size={12} />,
    statistics: <Box size={12} />,
  };

  return (
    <CollapsibleSection
      id="graph"
      icon={<Waypoints size={18} />}
      label="Knowledge Graph"
      description="Visualize and explore your knowledge"
      href={getWorkspacePath(currentWorkspaceId, '/graph')}
      collapsed={collapsed}
    >
      <div className="flex items-center gap-0.5 px-1 pb-1">
        <button
          onClick={() => router.push(getWorkspacePath(currentWorkspaceId, '/graph'))}
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="Refresh"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {availableGraphs.length > 0 && (
        <div className="px-1 pb-2">
          <p className="mb-1 px-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Graphs
          </p>
          <div className="space-y-0.5">
            {availableGraphs.map((graph) => (
              <GraphItemRow
                key={graph.id}
                graph={graph}
                isVisible={visibleGraphIds.includes(graph.id)}
                onToggle={() => toggleGraphVisibility(graph.id)}
                onClick={() => {
                  if (!visibleGraphIds.includes(graph.id)) {
                    toggleGraphVisibility(graph.id);
                  }
                  router.push(getWorkspacePath(currentWorkspaceId, '/graph'));
                }}
              />
            ))}
          </div>
        </div>
      )}

      <div className="px-1 pb-2">
        <p className="mb-1 px-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Views
        </p>
        <div className="space-y-0.5">
          {(['visual', 'table', 'sparql', 'schema', 'statistics'] as const).map((view) => (
            <button
              key={view}
              onClick={() => {
                setActiveViewType(view);
                router.push(getWorkspacePath(currentWorkspaceId, '/graph'));
              }}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors capitalize',
                activeViewType === view
                  ? 'bg-workspace-accent-10 text-workspace-accent'
                  : 'hover:bg-muted'
              )}
            >
              {viewIcons[view]}
              <span>{view}</span>
            </button>
          ))}
        </div>
      </div>
    </CollapsibleSection>
  );
}
