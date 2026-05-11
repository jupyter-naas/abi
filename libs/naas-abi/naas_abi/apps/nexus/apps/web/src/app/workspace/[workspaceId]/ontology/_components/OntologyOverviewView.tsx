'use client';

import { useMemo, useState } from 'react';
import { Box, Link2, Loader2, Search, X } from 'lucide-react';
import { useOntologyOverviewStats } from '../_hooks/use-ontology-queries';
import type {
  OntologyOverviewGraphEdge,
  OntologyOverviewGraphNode,
} from './types';

export interface OntologyOverviewViewProps {
  ontologyPath: string | null;
  graphNodes: OntologyOverviewGraphNode[];
  graphEdges: OntologyOverviewGraphEdge[];
  loadingGraph: boolean;
  graphError: string | null;
  onSelectClass: (classId: string) => void;
  onSelectRelationship: (relationshipId: string) => void;
  onCreateEntity: () => void;
  onCreateRelationship: () => void;
}

export function OntologyOverviewView({
  ontologyPath,
  graphNodes,
  graphEdges,
  loadingGraph,
  graphError,
  onSelectClass,
  onSelectRelationship,
  onCreateEntity,
  onCreateRelationship,
}: OntologyOverviewViewProps) {
  const statsQuery = useOntologyOverviewStats(ontologyPath);
  const stats = statsQuery.data ?? null;
  const loadingStats = statsQuery.isPending;
  const statsError = statsQuery.error ? 'Failed to load overview counts.' : null;
  const [listSearchQuery, setListSearchQuery] = useState('');
  const isAllOntologiesOverview = !ontologyPath;

  const classTableNodes = useMemo(() => {
    if (!isAllOntologiesOverview) return graphNodes;
    return graphNodes.filter((node) => node.type.toLowerCase() === 'ontology');
  }, [graphNodes, isAllOntologiesOverview]);

  const filteredClasses = useMemo(() => {
    if (!listSearchQuery.trim()) return classTableNodes;
    const q = listSearchQuery.toLowerCase();
    return classTableNodes.filter(
      (node) =>
        node.label.toLowerCase().includes(q) ||
        node.id.toLowerCase().includes(q) ||
        node.type.toLowerCase().includes(q),
    );
  }, [classTableNodes, listSearchQuery]);

  const graphNodesById = useMemo(
    () => new Map(graphNodes.map((node) => [node.id, node])),
    [graphNodes],
  );
  const filteredRelations = useMemo(() => {
    if (!listSearchQuery.trim()) return graphEdges;
    const q = listSearchQuery.toLowerCase();
    return graphEdges.filter((edge) => {
      const fromLabel = graphNodesById.get(edge.source)?.label ?? edge.source;
      const toLabel = graphNodesById.get(edge.target)?.label ?? edge.target;
      const label = edge.label ?? edge.type ?? '';
      return (
        fromLabel.toLowerCase().includes(q) ||
        toLabel.toLowerCase().includes(q) ||
        label.toLowerCase().includes(q) ||
        edge.id.toLowerCase().includes(q)
      );
    });
  }, [graphEdges, graphNodesById, listSearchQuery]);

  return (
    <div className="flex min-h-full flex-col bg-card p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Metrics</h2>
          <p className="text-sm text-muted-foreground truncate" title={ontologyPath || 'All ontologies'}>
            {stats?.name || ontologyPath || 'All ontologies'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onCreateEntity}
            className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
          >
            <Box size={14} className="text-blue-500" />
            New Class
          </button>
          <button
            onClick={onCreateRelationship}
            className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
          >
            <Link2 size={14} className="text-green-500" />
            New Object Property
          </button>
        </div>
      </div>

      {loadingStats && (
        <div className="flex flex-1 items-center justify-center gap-2 text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Loading overview stats...
        </div>
      )}

      {!loadingStats && statsError && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300">
          {statsError}
        </div>
      )}

      {!loadingStats && !statsError && stats && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div className="rounded-lg border bg-background p-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Total Items</p>
              <p className="mt-1 text-2xl font-semibold">{stats.total_items}</p>
            </div>
            <div className="rounded-lg border bg-background p-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Classes</p>
              <p className="mt-1 text-2xl font-semibold">{stats.classes}</p>
            </div>
            <div className="rounded-lg border bg-background p-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Object Properties</p>
              <p className="mt-1 text-2xl font-semibold">{stats.relationships}</p>
            </div>
            <div className="rounded-lg border bg-background p-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Data Properties</p>
              <p className="mt-1 text-2xl font-semibold">{stats.data_properties}</p>
            </div>
            <div className="rounded-lg border bg-background p-4">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">Named Individuals</p>
              <p className="mt-1 text-2xl font-semibold">{stats.named_individuals}</p>
            </div>
          </div>

          <div className="mt-6 flex items-center gap-2">
            <div className="relative flex-1 max-w-xs">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={listSearchQuery}
                onChange={(e) => setListSearchQuery(e.target.value)}
                placeholder={isAllOntologiesOverview ? 'Search ontologies, classes, object properties...' : 'Search classes, object properties...'}
                className="w-full rounded-lg border bg-background py-2 pl-9 pr-4 text-sm outline-none focus:ring-2 focus:ring-primary"
              />
              {listSearchQuery && (
                <button
                  onClick={() => setListSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {loadingGraph ? (
            <div className="mt-6 flex items-center gap-2 text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              Loading classes and relations...
            </div>
          ) : graphError ? (
            <div className="mt-6 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-900/20 dark:text-red-300">
              {graphError}
            </div>
          ) : (
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <div className="rounded-lg border bg-background">
                <div className="border-b px-4 py-3">
                  <h3 className="text-sm font-medium">
                    {isAllOntologiesOverview ? 'Ontologies' : 'Classes'}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {filteredClasses.length} of {classTableNodes.length}
                  </p>
                </div>
                <div className="max-h-80 overflow-y-auto p-2">
                  {filteredClasses.length === 0 ? (
                    <p className="p-4 text-center text-sm text-muted-foreground">
                      {isAllOntologiesOverview ? 'No ontologies found.' : 'No classes found.'}
                    </p>
                  ) : (
                    <ul className="space-y-1">
                      {filteredClasses.map((node) => {
                        const definition = isAllOntologiesOverview
                          ? ((node.properties?.comment || node.properties?.description) as string | undefined)
                          : (node.properties?.definition as string | undefined);
                        const definitionText = definition?.trim() || (isAllOntologiesOverview ? 'No description' : 'No definition');
                        return (
                          <li key={node.id}>
                            <button
                              onClick={() => onSelectClass(node.id)}
                              className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                            >
                              <Box size={14} className="mt-0.5 flex-shrink-0 text-blue-500" />
                              <div className="min-w-0 flex-1">
                                <span className="font-medium">{node.label}</span>
                                <p className="text-xs text-muted-foreground line-clamp-2" title={definitionText}>
                                  {definitionText}
                                </p>
                              </div>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </div>

              <div className="rounded-lg border bg-background">
                <div className="border-b px-4 py-3">
                  <h3 className="text-sm font-medium">
                    {isAllOntologiesOverview ? 'Imports' : 'Object Properties'}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {filteredRelations.length} of {graphEdges.length}
                  </p>
                </div>
                <div className="max-h-80 overflow-y-auto p-2">
                  {filteredRelations.length === 0 ? (
                    <p className="p-4 text-center text-sm text-muted-foreground">
                      No object properties found.
                    </p>
                  ) : (
                    <ul className="space-y-1">
                      {filteredRelations.map((edge) => (
                        <li key={edge.id}>
                          <button
                            onClick={() => onSelectRelationship(edge.id)}
                            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                          >
                            <Link2 size={14} className="flex-shrink-0 text-green-500" />
                            <span className="truncate">
                              {graphNodesById.get(edge.source)?.label ?? edge.source}
                            </span>
                            <span className="text-muted-foreground">→</span>
                            <span className="truncate font-medium">{edge.label ?? edge.type}</span>
                            <span className="text-muted-foreground">→</span>
                            <span className="truncate">
                              {graphNodesById.get(edge.target)?.label ?? edge.target}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
