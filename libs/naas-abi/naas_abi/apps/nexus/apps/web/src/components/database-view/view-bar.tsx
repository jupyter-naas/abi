'use client';

import { useState, type ReactNode } from 'react';
import {
  ArrowUpDown, ChevronDown, Copy, Eye, EyeOff, Filter as FilterIcon, Group,
  MoreHorizontal, Plus, Search, Settings2, Trash2, ArrowUp, ArrowDown, X,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { MenuSelect, Popover, ToolbarButton } from './primitives';
import type { DatabaseViewsApi } from './use-database-views';
import {
  FILTER_OPERATOR_LABELS, isBoundedType, operatorNeedsValue, operatorsFor,
  type DatabaseSchema, type Filter, type FilterOperator,
} from './model';

export interface ViewTypeDef<T extends string> {
  type: T;
  label: string;
  icon: LucideIcon;
}

function newFilterId(): string {
  return Math.random().toString(36).slice(2, 10);
}

// ---------------------------------------------------------------------------
// View tabs
// ---------------------------------------------------------------------------

function ViewTabs<K extends string, T extends string>({
  api,
  viewTypes,
  groupByForType,
}: {
  api: DatabaseViewsApi<K, T>;
  viewTypes: ViewTypeDef<T>[];
  groupByForType: (type: T, current: K | null) => K | null;
}) {
  const [renaming, setRenaming] = useState<string | null>(null);
  const [draftName, setDraftName] = useState('');
  const iconFor = (type: T) => viewTypes.find((v) => v.type === type)?.icon ?? Settings2;

  const commitRename = (id: string) => {
    api.renameView(id, draftName);
    setRenaming(null);
  };

  return (
    <div className="flex items-center gap-0.5 overflow-x-auto">
      {api.views.map((view) => {
        const Icon = iconFor(view.type);
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
                    {viewTypes.map(({ type, label, icon: TypeIcon }) => (
                      <button
                        key={type}
                        onClick={() => {
                          api.updateActiveView({ type, groupBy: groupByForType(type, view.groupBy) });
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
                        {label}
                      </button>
                    ))}
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
            {viewTypes.map(({ type, label, icon: TypeIcon }) => (
              <button
                key={type}
                onClick={() => {
                  api.addView(type);
                  close();
                }}
                className="flex w-full items-center gap-2 px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <TypeIcon size={13} />
                {label}
              </button>
            ))}
          </div>
        )}
      </Popover>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter menu
// ---------------------------------------------------------------------------

function FilterRow<R, K extends string>({
  schema,
  filter,
  records,
  onChange,
  onRemove,
}: {
  schema: DatabaseSchema<R, K>;
  filter: Filter<K>;
  records: R[];
  onChange: (next: Filter<K>) => void;
  onRemove: () => void;
}) {
  const def = schema.propertyByKey[filter.property];
  const operators = operatorsFor(def.type);
  const options = isBoundedType(def.type) ? schema.facetValues(records, filter.property) : null;

  return (
    <div className="space-y-1 border border-border/60 bg-muted/20 p-2">
      <div className="flex items-center gap-1">
        <MenuSelect
          className="flex-1"
          value={filter.property}
          onChange={(value) => {
            const nextDef = schema.propertyByKey[value as K];
            const nextOperators = operatorsFor(nextDef.type);
            onChange({
              ...filter,
              property: value as K,
              operator: nextOperators.includes(filter.operator) ? filter.operator : nextOperators[0],
              value: '',
            });
          }}
        >
          {schema.optionalProperties.map((property) => (
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

export function ViewBar<R, K extends string, T extends string>({
  api,
  schema,
  viewTypes,
  records,
  search,
  onSearchChange,
  count,
  countLabel,
  defaultFilterProperty,
  groupedTypes = [],
  defaultGroupBy,
  actions,
  tabs,
  iconOnly = false,
  singleRow = false,
}: {
  api: DatabaseViewsApi<K, T>;
  schema: DatabaseSchema<R, K>;
  viewTypes: ViewTypeDef<T>[];
  /** Unfiltered rows — filter menus offer the values that actually exist. */
  records: R[];
  search: string;
  onSearchChange: (value: string) => void;
  /** Records shown; left out, the bar shows no count. */
  count?: number;
  /** "3 apps", "1 task". */
  countLabel?: (count: number) => string;
  defaultFilterProperty: K;
  /** Layouts that always need a grouping axis (a board's columns). */
  groupedTypes?: T[];
  /** Axis a grouped layout falls back to when the view has none. */
  defaultGroupBy?: K;
  /** Extra controls at the end of the bar (e.g. a "New" button). */
  actions?: ReactNode;
  /** Replaces the saved-view tabs (the page picks what the tabs mean). */
  tabs?: ReactNode;
  /** Filter, Sort, Group and Properties as icons only (name in the tooltip). */
  iconOnly?: boolean;
  /** Tabs and tools on one row at any width: the tabs scroll, the tools stay compact. */
  singleRow?: boolean;
}) {
  const view = api.activeView;
  const activeFilters = view.filters.length;
  const alwaysGrouped = groupedTypes.includes(view.type);

  const groupByForType = (type: T, current: K | null): K | null =>
    groupedTypes.includes(type) ? current ?? defaultGroupBy ?? null : current;

  const setFilters = (filters: Filter<K>[]) => api.updateActiveView({ filters });

  const toggleProperty = (key: K) => {
    const visible = view.visible.includes(key)
      ? view.visible.filter((k) => k !== key)
      : [...view.visible, key];
    api.updateActiveView({ visible });
  };

  const moveProperty = (key: K, delta: number) => {
    const index = view.visible.indexOf(key);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= view.visible.length) return;
    const visible = [...view.visible];
    [visible[index], visible[target]] = [visible[target], visible[index]];
    api.updateActiveView({ visible });
  };

  const titleLabel = schema.propertyByKey[schema.titleKey].label;

  return (
    <div
      className={cn(
        'flex items-center border-b border-border/50',
        singleRow ? 'flex-nowrap gap-2 px-2 sm:px-4' : 'flex-wrap gap-x-2 gap-y-1 px-4',
      )}
    >
      {singleRow ? (
        <div className="min-w-0 flex-1">
          {tabs ?? <ViewTabs api={api} viewTypes={viewTypes} groupByForType={groupByForType} />}
        </div>
      ) : (
        (tabs ?? <ViewTabs api={api} viewTypes={viewTypes} groupByForType={groupByForType} />)
      )}

      <div className={cn('ml-auto flex items-center gap-1 py-1', singleRow && 'shrink-0')}>
        {count !== undefined && countLabel && (
          <span className="hidden pr-1 text-xs text-muted-foreground sm:inline">{countLabel(count)}</span>
        )}

        <div className="relative">
          <Search size={13} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search"
            className={cn(
              'h-8 border bg-background pl-7 pr-2 text-xs focus:outline-none',
              singleRow
                ? // Neutral border while typing: no colored ring.
                  'w-48 focus:w-72 focus:ring-0 focus-visible:ring-0 sm:w-64 sm:focus:w-[22rem]'
                : 'w-36 focus:w-52 focus:ring-1 focus:ring-workspace-accent/40',
            )}
          />
        </div>

        {/* Filters */}
        <Popover
          align="right"
          width="w-80"
          trigger={({ toggle }) => (
            <ToolbarButton onClick={toggle} active={activeFilters > 0} title="Filter" aria-label="Filter">
              <FilterIcon size={13} />
              {!iconOnly && 'Filter'}
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
                schema={schema}
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
                    { id: newFilterId(), property: defaultFilterProperty, operator: 'is', value: '' },
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
            <ToolbarButton onClick={toggle} active={!!view.sort} title="Sort" aria-label="Sort">
              <ArrowUpDown size={13} />
              {!iconOnly && 'Sort'}
            </ToolbarButton>
          )}
        >
          <div className="space-y-2">
            <p className="px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Sort by
            </p>
            <MenuSelect
              value={view.sort?.property ?? schema.titleKey}
              onChange={(value) =>
                api.updateActiveView({
                  sort: { property: value as K, direction: view.sort?.direction ?? 'asc' },
                })
              }
            >
              <option value={schema.titleKey}>{titleLabel}</option>
              {schema.optionalProperties.map((property) => (
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
                    property: view.sort?.property ?? schema.titleKey,
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
                Reset to {titleLabel.toLowerCase()}
              </button>
            )}
          </div>
        </Popover>

        {/* Group */}
        <Popover
          align="right"
          width="w-56"
          trigger={({ toggle }) => (
            <ToolbarButton onClick={toggle} active={!!view.groupBy} title="Group" aria-label="Group">
              <Group size={13} />
              {!iconOnly && 'Group'}
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
                disabled={alwaysGrouped}
                className={cn(
                  'flex w-full items-center px-2 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                  view.groupBy === null
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )}
              >
                None
              </button>
              {schema.groupableProperties.map((property) => (
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
              {alwaysGrouped && (
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
            <ToolbarButton onClick={toggle} title="Properties" aria-label="Properties">
              <Settings2 size={13} />
              {!iconOnly && 'Properties'}
            </ToolbarButton>
          )}
        >
          <div className="space-y-1">
            <p className="px-1 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              Shown
            </p>
            {view.visible.length === 0 && (
              <p className="px-1 pb-1 text-xs text-muted-foreground">
                Only the {titleLabel.toLowerCase()} is shown.
              </p>
            )}
            {view.visible.map((key, index) => (
              <div key={key} className="flex items-center gap-1 px-1 py-0.5">
                <span className="flex-1 truncate text-sm">{schema.propertyByKey[key].label}</span>
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
            {schema.optionalProperties
              .filter((property) => !view.visible.includes(property.key))
              .map((property) => (
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
              ))}
          </div>
        </Popover>

        {actions}
      </div>
    </div>
  );
}
