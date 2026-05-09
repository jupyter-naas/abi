'use client';

import { useEffect, useMemo, useState } from 'react';
import { Box, ChevronRight, Link2, Plus, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { OntologyItem, ReferenceClass } from '@/stores/ontology';
import { EntityDetailView } from './EntityDetailView';

export interface OntologySplitViewProps {
  mode: 'classes' | 'relations';
  items: OntologyItem[];
  selectedItemId: string | null;
  selectedItem?: OntologyItem;
  onSelectItem: (itemId: string | null) => void;
  allClasses: Array<ReferenceClass & { ontologyName: string }>;
  onUpdateItem: (itemId: string, updates: Partial<OntologyItem>) => void;
  onCreateEntity: () => void;
  onCreateRelationship: () => void;
}

type TreeNode = { item: OntologyItem; children: TreeNode[] };

export function OntologySplitView({
  mode,
  items,
  selectedItemId,
  selectedItem,
  onSelectItem,
  allClasses,
  onUpdateItem,
  onCreateEntity,
  onCreateRelationship,
}: OntologySplitViewProps) {
  const [query, setQuery] = useState('');
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());
  const [didInitExpanded, setDidInitExpanded] = useState(false);
  const isClassMode = mode === 'classes';
  const modeLabel = isClassMode ? 'Classes' : 'Object Properties';
  const ModeIcon = isClassMode ? Box : Link2;

  useEffect(() => {
    if (!didInitExpanded && items.length > 0) {
      setExpandedNodeIds(new Set(items.map((item) => item.id)));
      setDidInitExpanded(true);
    }
  }, [didInitExpanded, items]);

  const visibleItemIds = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return new Set(items.map((item) => item.id));
    }

    const matchingIds = new Set(
      items
        .filter(
          (item) =>
            item.name.toLowerCase().includes(normalizedQuery) ||
            item.description?.toLowerCase().includes(normalizedQuery),
        )
        .map((item) => item.id),
    );

    // Keep ancestors visible so search results remain in hierarchy context.
    const byId = new Map(items.map((item) => [item.id, item]));
    for (const matchId of Array.from(matchingIds)) {
      let current = byId.get(matchId);
      const seen = new Set<string>();
      while (current?.parentId && !seen.has(current.parentId)) {
        seen.add(current.parentId);
        matchingIds.add(current.parentId);
        current = byId.get(current.parentId);
      }
    }

    return matchingIds;
  }, [items, query]);

  const hierarchicalItems = useMemo(() => {
    const visibleItems = items.filter((item) => visibleItemIds.has(item.id));
    const byId = new Map(visibleItems.map((item) => [item.id, item]));
    const childrenByParent = new Map<string | null, OntologyItem[]>();

    const attach = (parentKey: string | null, item: OntologyItem) => {
      const current = childrenByParent.get(parentKey) || [];
      current.push(item);
      childrenByParent.set(parentKey, current);
    };

    visibleItems.forEach((item) => {
      const parentKey = item.parentId && byId.has(item.parentId) ? item.parentId : null;
      attach(parentKey, item);
    });

    const sortByName = (list: OntologyItem[]) =>
      [...list].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));

    const buildNodes = (parentKey: string | null, ancestry: Set<string>): TreeNode[] => {
      return sortByName(childrenByParent.get(parentKey) || []).map((item) => {
        if (ancestry.has(item.id)) {
          return { item, children: [] };
        }
        const nextAncestry = new Set(ancestry);
        nextAncestry.add(item.id);
        return { item, children: buildNodes(item.id, nextAncestry) };
      });
    };

    return buildNodes(null, new Set<string>());
  }, [items, visibleItemIds]);

  const searchExpandedNodeIds = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return new Set<string>();

    const byId = new Map(items.map((item) => [item.id, item]));
    const autoExpanded = new Set<string>();

    items.forEach((item) => {
      const isMatch =
        item.name.toLowerCase().includes(normalizedQuery) ||
        item.description?.toLowerCase().includes(normalizedQuery);
      if (!isMatch) return;

      let current = item;
      const seen = new Set<string>();
      while (current.parentId && !seen.has(current.parentId)) {
        seen.add(current.parentId);
        autoExpanded.add(current.parentId);
        const parent = byId.get(current.parentId);
        if (!parent) break;
        current = parent;
      }
    });

    return autoExpanded;
  }, [items, query]);

  const selectedItemInMode = useMemo(() => {
    const expectedType: OntologyItem['type'] = isClassMode ? 'entity' : 'relationship';
    if (!selectedItemId) return undefined;
    const inViewItem = items.find((item) => item.id === selectedItemId);
    if (inViewItem && inViewItem.type === expectedType) return inViewItem;
    if (selectedItem && selectedItem.id === selectedItemId && selectedItem.type === expectedType) {
      return selectedItem;
    }
    return undefined;
  }, [isClassMode, items, selectedItem, selectedItemId]);

  return (
    <div className="flex flex-1 overflow-hidden bg-card">
      <div className="flex w-80 flex-shrink-0 flex-col border-r bg-muted/20">
        <div className="border-b p-4">
          <div className="mb-3 flex items-center gap-2">
            <ModeIcon size={18} className={isClassMode ? 'text-blue-500' : 'text-green-500'} />
            <h2 className="font-semibold">{modeLabel}</h2>
            <span className="text-xs text-muted-foreground">({items.length})</span>
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={`Search ${modeLabel.toLowerCase()}...`}
              className="w-full rounded-md border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
        </div>

        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {hierarchicalItems.length === 0 ? (
            <p className="px-2 py-4 text-center text-sm text-muted-foreground">
              No {modeLabel.toLowerCase()} found.
            </p>
          ) : (
            hierarchicalItems.map((node) => {
              const renderNode = (current: TreeNode, depth: number) => (
                <div key={current.item.id}>
                  {(() => {
                    const hasChildren = current.children.length > 0;
                    const isExpanded =
                      expandedNodeIds.has(current.item.id) ||
                      searchExpandedNodeIds.has(current.item.id);

                    return (
                      <>
                        <button
                          type="button"
                          onClick={() => onSelectItem(current.item.id)}
                          className={cn(
                            'flex w-full items-center gap-1 rounded-md py-1 pr-2 text-left text-sm transition-colors',
                            selectedItemInMode?.id === current.item.id
                              ? 'bg-workspace-accent-10 text-workspace-accent'
                              : 'hover:bg-background',
                          )}
                          style={{ paddingLeft: `${8 + depth * 16}px` }}
                          title={current.item.description}
                        >
                          {hasChildren ? (
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                setExpandedNodeIds((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(current.item.id)) {
                                    next.delete(current.item.id);
                                  } else {
                                    next.add(current.item.id);
                                  }
                                  return next;
                                });
                              }}
                              className="rounded p-0.5 text-muted-foreground hover:bg-muted"
                            >
                              <ChevronRight
                                size={14}
                                className={cn('transition-transform', isExpanded && 'rotate-90')}
                              />
                            </button>
                          ) : (
                            <span className="w-[18px]" />
                          )}

                          <span className="flex flex-1 items-center gap-2 py-1 text-left">
                            <ModeIcon
                              size={14}
                              className={isClassMode ? 'text-blue-500' : 'text-green-500'}
                            />
                            <span className="truncate">{current.item.name}</span>
                          </span>
                        </button>
                        {hasChildren &&
                          isExpanded &&
                          current.children.map((child) => renderNode(child, depth + 1))}
                      </>
                    );
                  })()}
                </div>
              );

              return renderNode(node, 0);
            })
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {selectedItemInMode ? (
          <EntityDetailView
            item={selectedItemInMode}
            allClasses={allClasses}
            onUpdate={(updates) => onUpdateItem(selectedItemInMode.id, updates)}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <div className="text-center">
              <div className="mb-4 flex justify-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
                  <ModeIcon
                    size={32}
                    className={isClassMode ? 'text-blue-500' : 'text-green-500'}
                  />
                </div>
              </div>
              <h2 className="mb-2 text-lg font-semibold">{modeLabel} Editor</h2>
              <p className="mb-6 max-w-md text-muted-foreground">
                Select a {isClassMode ? 'class' : 'object property'} from the left list or create a
                new {isClassMode ? 'class' : 'object property'}.
              </p>
              <div className="flex justify-center gap-3">
                <button
                  onClick={isClassMode ? onCreateEntity : onCreateRelationship}
                  className={cn(
                    'flex items-center gap-2 rounded-lg bg-workspace-accent px-4 py-2 text-sm font-medium text-white',
                    'hover:opacity-90',
                  )}
                >
                  <Plus size={16} />
                  {isClassMode ? 'New Class' : 'New Object Property'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
