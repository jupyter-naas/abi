'use client';

import { useState } from 'react';
import {
  ArrowUpDown, ChevronDown, Copy, Eye, EyeOff, Filter as FilterIcon, Group,
  LayoutGrid, List, MoreHorizontal, Plus, Search, Settings2, Table2, Trash2,
  Columns3, ArrowUp, ArrowDown, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { MenuSelect, Popover, ToolbarButton } from './primitives';
import type { AppViewsApi } from './use-app-views';
import {
  FILTER_OPERATOR_LABELS, GROUPABLE_PROPERTIES, OPTIONAL_PROPERTIES,
  PROPERTY_BY_KEY, VIEW_TYPE_LABELS, facetValues, operatorNeedsValue, operatorsFor,
  type AppRecord, type Filter, type FilterOperator, type PropertyKey, type ViewType,
} from './types';

const VIEW_TYPE_ICONS: Record<ViewType, typeof LayoutGrid> = {
  gallery: LayoutGrid,
  table: Table2,
  list: List,
  board: Columns3,
};

const VIEW_TYPES: ViewType[] = ['gallery', 'table', 'list', 'board'];

function newFilterId(): string {
  return Math.random().toString(36).slice(2, 10);
}

// ---------------------------------------------------------------------------
// View tabs
// ---------------------------------------------------------------------------

function ViewTabs({ api }: { api: AppViewsApi }) {
  const [renaming, setRenaming] = useState<string | null>(null);
  const [draftName, setDraftName] = useState('');

  const commitRename = (id: string) => {
    api.renameView(id, draftName);
    setRenaming(null);
  };

  return (
    <div className="flex items-center gap-0.5 overflow-x-auto">
      {api.views.map((view) => {
        const Icon = VIEW_TYPE_ICONS[view.type];
        const isActive = view.id === api.activeViewId;

        if (renaming === view.id) {
          return (
            <input
              key={view.id}
              autoFocus
              value={draftName}
              onChange={(e) => setDraftName(e.target.value)}
              onBlur={() => commitRename(view.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitRename(view.id);
                if (e.key === 'Escape') setRenaming(null);
              }}
              className="h-8 w-32 border bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-workspace-accent/40"
            />
          );
        }

        return (
          <div key={view.id} className="flex items-center">
            <button
              onClick={() => api.selectView(view.id)}
              onDoubleClick={() => {
                setDraftName(view.name);
                setRenaming(view.id);
              }}
              className={cn(
                'flex h-8 items-center gap-1.5 whitespace-nowrap px-2 text-sm transition-colors',
                isActive
                  ? 'border-b-2 border-foreground font-medium text-foreground'
                  : 'border-b-2 border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              <Icon size={13} />
              {view.name}
            </button>
            {isActive && (
              <Popover
                width="w-52"
                trigger={({ toggle }) => (
                  <button
                    onClick={toggle}
                    title="View options"
                    className="flex h-8 w-6 items-center justify-center text-muted-foreground hover:text-foreground"
                  >
                    <ChevronDown size={12} />
                  </button>
                )}
              >
                {(close) => (
                  <div className="space-y-1">
                    <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Layout
                    </p>
                    {VIEW_TYPES.map((type) => {
                      const TypeIcon = VIEW_TYPE_ICONS[type];
                      return (
                        <button
                          key={type}
                          onClick={() => {
                            api.updateActiveView({
                              type,
                              groupBy: type === 'board' ? view.groupBy ?? 'module' : view.groupBy,
                            });
                            close();
                          }}
                          className={cn(
                            'flex w-full items-center gap-2 px-2 py-1.5 text-sm transition-colors',
                            view.type === type
                              ? 'bg-muted text-foreground'
                              : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                          )}
                        >
                          <TypeIcon size={13} />
                          {VIEW_TYPE_LABELS[type]}
                        </button>
                      );
                    })}
                    <div className="my-1 border-t border-border/60" />
                    <button
                      onClick={() => {
                        setDraftName(view.name);
                        setRenaming(view.id);
                        close();
                      }}
                      className="flex w-full items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      <MoreHorizontal size={13} /> Rename
                    </button>
                    <button
                      onClick={() => {
                        api.duplicateView(view.id);
                        close();
                      }}
                      className="flex w-full items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      <Copy size={13} /> Duplicate
                    </button>
                    <button
                      disabled={api.views.length <= 1}
                      onClick={() => {
                        api.deleteView(view.id);
                        close();
                      }}
                      className="flex w-full items-center gap-2 px-2 py-1.5 text-sm text-destructive transition-colors hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <Trash2 size={13} /> Delete view
                    </button>
                  </div>
                )}
              </Popover>
            )}
          </div>
        );
      })}

      <Popover
        width="w-44"
        trigger={({ toggle }) => (
          <button
            onClick={toggle}
            title="Add a view"
            className="flex h-8 w-7 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
          >
            <Plus size={14} />
          </button>
        )}
      >
        {(close) => (
          <div className="space-y-1">
            <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              New view
            </p>
            {VIEW_TYPES.map((type) => {
              const TypeIcon = VIEW_TYPE_ICONS[type];
              return (
                <button
                  key={type}
                  onClick={() => {
                    api.addView(type);
                    close();
                  }}
                  className="flex w-full items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <TypeIcon size={13} />
                  {VIEW_TYPE_LABELS[type]}
                </button>
              );
            })}
          </div>
        )}
      </Popover>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter menu
// ---------------------------------------------------------------------------

function FilterRow({
  filter,
  records,
  onChange,
  onRemove,
}: {
  filter: Filter;
  records: AppRecord[];
  onChange: (next: Filter) => void;
  onRemove: () => void;
}) {
  const def = PROPERTY_BY_KEY[filter.property];
  const operators = operatorsFor(def.type);
  const options = def.type === 'select' || def.type === 'multi' ? facetValues(records, filter.property) : null;

  return (
    <div className="space-y-1 border border-border/60 bg-muted/20 p-2">
      <div className="flex items-center gap-1">
        <MenuSelect
          className="flex-1"
          value={filter.property}
          onChange={(value) => {
            const nextDef = PROPERTY_BY_KEY[value as PropertyKey];
            const nextOperators = operatorsFor(nextDef.type);
            onChange({
              ...filter,
              property: value as PropertyKey,
              operator: nextOperators.includes(filter.operator) ? filter.operator : nextOperators[0],
              value: '',
            });
          }}
        >
          {OPTIONAL_PROPERTIES.map((property) => (
            <option key={property.key} value={property.key}>
              {property.label}
            </option>
          ))}
        </MenuSelect>
        <button
          onClick={onRemove}
          title="Remove filter"
          className="flex h-7 w-7 flex-shrink-0 items-center justify-center text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <X size={12} />
        </button>
      </div>
      <MenuSelect
        value={filter.operator}
        onChange={(value) => onChange({ ...filter, operator: value as FilterOperator })}
      >
        {operators.map((operator) => (
          <option key={operator} value={operator}>
            {FILTER_OPERATOR_LABELS[operator]}
          </option>
        ))}
      </MenuSelect>
      {operatorNeedsValue(filter.operator) &&
        (options && filter.operator !== 'contains' && filter.operator !== 'not_contains' ? (
          <MenuSelect value={filter.value} onChange={(value) => onChange({ ...filter, value })}>
            <option value="">Select a value…</option>
            {options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </MenuSelect>
        ) : (
          <input
            value={filter.value}
            onChange={(e) => onChange({ ...filter, value: e.target.value })}
            placeholder="Value…"
            className="h-7 w-full border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-workspace-accent/40"
          />
        ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View bar
// ---------------------------------------------------------------------------

export function ViewBar({
  api,
  records,
  search,
  onSearchChange,
  count,
}: {
  api: AppViewsApi;
  /** Unfiltered rows — filter menus offer the values that actually exist. */
  records: AppRecord[];
  search: string;
  onSearchChange: (value: string) => void;
  count: number;
}) {
  const view = api.activeView;
  const activeFilters = view.filters.length;

  const setFilters = (filters: Filter[]) => api.updateActiveView({ filters });

  const toggleProperty = (key: PropertyKey) => {
    const visible = view.visible.includes(key)
      ? view.visible.filter((k) => k !== key)
      : [...view.visible, key];
    api.updateActiveView({ visible });
  };

  const moveProperty = (key: PropertyKey, delta: number) => {
    const index = view.visible.indexOf(key);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= view.visible.length) return;
    const visible = [...view.visible];
    [visible[index], visible[target]] = [visible[target], visible[index]];
    api.updateActiveView({ visible });
  };

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-border/50 px-4">
      <ViewTabs api={api} />

      <div className="ml-auto flex items-center gap-1 py-1">
        <span className="hidden pr-1 text-xs text-muted-foreground sm:inline">
          {count} {count === 1 ? 'app' : 'apps'}
        </span>

        <div className="relative">
          <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search"
            className="h-8 w-36 border bg-background pl-7 pr-2 text-xs focus:w-52 focus:outline-none focus:ring-1 focus:ring-workspace-accent/40"
          />
        </div>

        {/* Filters */}
        <Popover
          align="right"
          width="w-80"
          trigger={({ toggle }) => (
            <ToolbarButton onClick={toggle} active={activeFilters > 0}>
              <FilterIcon size={13} />
              Filter
              {activeFilters > 0 && <span className="text-[10px]">({activeFilters})</span>}
            </ToolbarButton>
          )}
        >
          <div className="space-y-2">
            <p className="px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Filters
            </p>
            {view.filters.length === 0 && (
              <p className="px-1 pb-1 text-xs text-muted-foreground">
                No filters. Rows are shown as they come.
              </p>
            )}
            {view.filters.map((filter) => (
              <FilterRow
                key={filter.id}
                filter={filter}
                records={records}
                onChange={(next) => setFilters(view.filters.map((f) => (f.id === filter.id ? next : f)))}
                onRemove={() => setFilters(view.filters.filter((f) => f.id !== filter.id))}
              />
            ))}
            <div className="flex items-center justify-between pt-1">
              <button
                onClick={() =>
                  setFilters([
                    ...view.filters,
                    { id: newFilterId(), property: 'category', operator: 'is', value: '' },
                  ])
                }
                className="flex items-center gap-1 px-1 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                <Plus size={12} /> Add filter
              </button>
              {view.filters.length > 0 && (
                <button
                  onClick={() => setFilters([])}
                  className="px-1 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                >
                  Clear all
                </button>
              )}
            </div>
          </div>
        </Popover>

        {/* Sort */}
        <Popover
          align="right"
          width="w-64"
          trigger={({ toggle }) => (
            <ToolbarButton onClick={toggle} active={!!view.sort}>
              <ArrowUpDown size={13} />
              Sort
            </ToolbarButton>
          )}
        >
          <div className="space-y-2">
            <p className="px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Sort by
            </p>
            <MenuSelect
              value={view.sort?.property ?? 'name'}
              onChange={(value) =>
                api.updateActiveView({
                  sort: { property: value as PropertyKey, direction: view.sort?.direction ?? 'asc' },
                })
              }
            >
              <option value="name">Name</option>
              {OPTIONAL_PROPERTIES.map((property) => (
                <option key={property.key} value={property.key}>
                  {property.label}
                </option>
              ))}
            </MenuSelect>
            <MenuSelect
              value={view.sort?.direction ?? 'asc'}
              onChange={(value) =>
                api.updateActiveView({
                  sort: {
                    property: view.sort?.property ?? 'name',
                    direction: value as 'asc' | 'desc',
                  },
                })
              }
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </MenuSelect>
            {view.sort && (
              <button
                onClick={() => api.updateActiveView({ sort: null })}
                className="px-1 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                Reset to name
              </button>
            )}
          </div>
        </Popover>

        {/* Group */}
        <Popover
          align="right"
          width="w-56"
          trigger={({ toggle }) => (
            <ToolbarButton onClick={toggle} active={!!view.groupBy}>
              <Group size={13} />
              Group
            </ToolbarButton>
          )}
        >
          {(close) => (
            <div className="space-y-1">
              <p className="px-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Group by
              </p>
              <button
                onClick={() => {
                  api.updateActiveView({ groupBy: null });
                  close();
                }}
                disabled={view.type === 'board'}
                className={cn(
                  'flex w-full items-center px-2 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                  view.groupBy === null
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                None
              </button>
              {GROUPABLE_PROPERTIES.map((property) => (
                <button
                  key={property.key}
                  onClick={() => {
                    api.updateActiveView({ groupBy: property.key });
                    close();
                  }}
                  className={cn(
                    'flex w-full items-center px-2 py-1.5 text-sm transition-colors',
                    view.groupBy === property.key
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )}
                >
                  {property.label}
                </button>
              ))}
              {view.type === 'board' && (
                <p className="px-2 pt-1 text-[11px] text-muted-foreground">
                  A board is always grouped.
                </p>
              )}
            </div>
          )}
        </Popover>

        {/* Properties */}
        <Popover
          align="right"
          width="w-64"
          trigger={({ toggle }) => (
            <ToolbarButton onClick={toggle}>
              <Settings2 size={13} />
              Properties
            </ToolbarButton>
          )}
        >
          <div className="space-y-1">
            <p className="px-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Shown
            </p>
            {view.visible.length === 0 && (
              <p className="px-1 pb-1 text-xs text-muted-foreground">Only the name is shown.</p>
            )}
            {view.visible.map((key, index) => (
              <div key={key} className="flex items-center gap-1 px-1 py-0.5">
                <span className="flex-1 truncate text-sm">{PROPERTY_BY_KEY[key].label}</span>
                <button
                  onClick={() => moveProperty(key, -1)}
                  disabled={index === 0}
                  title="Move up"
                  className="p-1 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                >
                  <ArrowUp size={11} />
                </button>
                <button
                  onClick={() => moveProperty(key, 1)}
                  disabled={index === view.visible.length - 1}
                  title="Move down"
                  className="p-1 text-muted-foreground transition-colors hover:text-foreground disabled:opacity-30"
                >
                  <ArrowDown size={11} />
                </button>
                <button
                  onClick={() => toggleProperty(key)}
                  title="Hide property"
                  className="p-1 text-muted-foreground transition-colors hover:text-foreground"
                >
                  <Eye size={12} />
                </button>
              </div>
            ))}

            <div className="my-1 border-t border-border/60" />
            <p className="px-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Hidden
            </p>
            {OPTIONAL_PROPERTIES.filter((property) => !view.visible.includes(property.key)).map(
              (property) => (
                <div key={property.key} className="flex items-center gap-1 px-1 py-0.5">
                  <span className="flex-1 truncate text-sm text-muted-foreground">{property.label}</span>
                  <button
                    onClick={() => toggleProperty(property.key)}
                    title="Show property"
                    className="p-1 text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <EyeOff size={12} />
                  </button>
                </div>
              ),
            )}
          </div>
        </Popover>
      </div>
    </div>
  );
}
