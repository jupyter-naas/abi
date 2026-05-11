'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  ChevronRight,
  Circle,
  Loader2,
  Search,
  UserPlus,
  Users,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { IndividualDetailPanel } from './IndividualDetailPanel';
import type { GraphEdge, GraphNode } from './types';

export interface IndividualsSplitViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  loading: boolean;
  error: string | null;
  onCreateIndividual: () => void;
}

export function IndividualsSplitView({
  nodes,
  edges,
  loading,
  error,
  onCreateIndividual,
}: IndividualsSplitViewProps) {
  const [selectedIndividualId, setSelectedIndividualId] = useState<string | null>(null);
  const [expandedClasses, setExpandedClasses] = useState<Set<string>>(new Set());
  const [didInitExpanded, setDidInitExpanded] = useState(false);
  const [search, setSearch] = useState('');

  // Group nodes by rdf:type (node.type = class label)
  const nodesByClass = useMemo(() => {
    const grouped = new Map<string, GraphNode[]>();
    for (const node of nodes) {
      const type = node.type || 'Unknown';
      if (!grouped.has(type)) grouped.set(type, []);
      grouped.get(type)!.push(node);
    }
    return new Map([...grouped.entries()].sort((a, b) => a[0].localeCompare(b[0])));
  }, [nodes]);

  useEffect(() => {
    if (!didInitExpanded && nodesByClass.size > 0) {
      setExpandedClasses(new Set(nodesByClass.keys()));
      setDidInitExpanded(true);
    }
  }, [didInitExpanded, nodesByClass]);

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedIndividualId) ?? null,
    [nodes, selectedIndividualId],
  );

  const dataProperties = useMemo(() => {
    if (!selectedNode) return [];
    const INTERNAL_KEYS = new Set(['bfo_parent_iri', 'is_class', 'x', 'y']);
    return Object.entries(selectedNode.properties)
      .filter(([k]) => !INTERNAL_KEYS.has(k))
      .map(([k, v]) => ({ predicate: k, value: String(v) }));
  }, [selectedNode]);

  const objectProperties = useMemo(() => {
    if (!selectedNode) return [];
    return edges
      .filter((e) => e.source === selectedNode.id)
      .map((e) => ({
        predicate: e.type,
        targetId: e.target,
        targetLabel: e.targetLabel ?? e.target,
      }));
  }, [selectedNode, edges]);

  const filteredNodesByClass = useMemo(() => {
    if (!search.trim()) return nodesByClass;
    const q = search.toLowerCase();
    const result = new Map<string, GraphNode[]>();
    for (const [cls, individuals] of nodesByClass) {
      const classMatches = cls.toLowerCase().includes(q);
      const matchingIndividuals = individuals.filter(
        (n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q),
      );
      if (classMatches || matchingIndividuals.length > 0) {
        result.set(cls, classMatches ? individuals : matchingIndividuals);
      }
    }
    return result;
  }, [nodesByClass, search]);

  const toggleClass = useCallback((cls: string) => {
    setExpandedClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  }, []);

  return (
    <div className="flex flex-1 overflow-hidden bg-card">
      <div className="flex w-80 flex-shrink-0 flex-col border-r bg-muted/20">
        <div className="border-b p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Users size={18} className="text-orange-500 dark:text-orange-400" />
              <h2 className="font-semibold">Individuals</h2>
              <span className="text-xs text-muted-foreground">({nodes.length})</span>
            </div>
            <button
              type="button"
              onClick={onCreateIndividual}
              className="flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs font-medium hover:bg-muted"
            >
              <UserPlus size={12} className="text-orange-500 dark:text-orange-400" />
              New
            </button>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search individuals..."
              className="w-full rounded-md border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        </div>

        <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">Loading…</span>
            </div>
          ) : error ? (
            <p className="px-2 py-4 text-center text-sm text-red-500">{error}</p>
          ) : filteredNodesByClass.size === 0 ? (
            <p className="px-2 py-4 text-center text-sm text-muted-foreground">
              No individuals found.
            </p>
          ) : (
            Array.from(filteredNodesByClass.entries()).map(([cls, individuals]) => {
              const isExpanded = expandedClasses.has(cls);
              const sorted = [...individuals].sort((a, b) =>
                a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }),
              );
              return (
                <div key={cls}>
                  <button
                    type="button"
                    onClick={() => toggleClass(cls)}
                    className="flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-left text-sm hover:bg-background"
                  >
                    <ChevronRight
                      size={14}
                      className={cn(
                        'flex-shrink-0 text-muted-foreground transition-transform',
                        isExpanded && 'rotate-90',
                      )}
                    />
                    <Box size={14} className="flex-shrink-0 text-blue-500" />
                    <span className="flex-1 truncate font-medium">{cls}</span>
                    <span className="text-xs text-muted-foreground">{individuals.length}</span>
                  </button>

                  {isExpanded &&
                    sorted.map((ind) => (
                      <button
                        key={ind.id}
                        type="button"
                        onClick={() => setSelectedIndividualId(ind.id)}
                        title={ind.id}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-md py-1 pl-8 pr-2 text-left text-sm transition-colors',
                          selectedIndividualId === ind.id
                            ? 'bg-workspace-accent-10 text-workspace-accent'
                            : 'hover:bg-background',
                        )}
                      >
                        <Circle size={10} className="flex-shrink-0 text-orange-500 dark:text-orange-400" />
                        <span className="truncate">{ind.label}</span>
                      </button>
                    ))}
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {selectedNode ? (
          <IndividualDetailPanel
            node={selectedNode}
            dataProperties={dataProperties}
            objectProperties={objectProperties}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center">
              <div className="mb-4 flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                  <Users size={32} className="text-orange-500 dark:text-orange-400" />
                </div>
              </div>
              <h2 className="mb-2 text-lg font-semibold">Individuals</h2>
              <p className="mb-6 max-w-md text-muted-foreground">
                Select an individual from the left panel to view its data and object
                properties, or create a new one.
              </p>
              <button
                onClick={onCreateIndividual}
                className="mx-auto flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                <UserPlus size={16} />
                Create Individual
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
