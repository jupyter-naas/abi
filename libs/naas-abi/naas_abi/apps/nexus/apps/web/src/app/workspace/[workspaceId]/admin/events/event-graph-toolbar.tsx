'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BFO_BUCKET_BY_TYPE } from '@/lib/bfo-buckets';
import {
  filterSummary,
  formatRangeBound,
  type EventGraphModel,
  type FilterGroup,
  type FilterInstance,
  type GraphFilters,
} from './event-graph-model';

/** The cockpit's `individual_search_min_chars`, relaxed for short verbs. */
const SEARCH_MIN_CHARS = 2;

function useDismissOnOutside(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) onClose();
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open, onClose]);
  return ref;
}

/**
 * The cockpit's process/class filter: a summary button opening a list of types,
 * each expandable to its instances, with select-all / clear-all at the foot.
 */
function FilterDropdown({
  title,
  groups,
  instances,
  hiddenTypes,
  hiddenInstances,
  onToggleType,
  onToggleInstance,
  onSelectAll,
  onClearAll,
}: {
  title: string;
  groups: FilterGroup[];
  instances: FilterInstance[];
  hiddenTypes: Set<string>;
  hiddenInstances: Set<string>;
  onToggleType: (label: string) => void;
  onToggleInstance: (id: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const ref = useDismissOnOutside(open, () => setOpen(false));
  const summary = filterSummary(instances, hiddenTypes, hiddenInstances);

  return (
    <div ref={ref} className="relative flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{title}</span>
      <button
        type="button"
        disabled={instances.length === 0}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        className={cn(
          'flex items-center gap-1 rounded border bg-background/80 px-2 py-1 text-[11px] hover:bg-workspace-accent-10 hover:text-workspace-accent disabled:opacity-50',
          // Open reads in the workspace accent. It used to be `bg-accent`,
          // which workspace-layout.tsx rewrites to the workspace colour at full
          // strength — black text on a black button in a dark theme.
          open && 'bg-workspace-accent-10 border-workspace-accent text-workspace-accent',
        )}
      >
        <span>{summary}</span>
        <ChevronDown size={11} className={cn('transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-30 mt-1 max-h-80 w-72 overflow-y-auto rounded-lg border bg-background p-1.5 shadow-lg">
          <ul className="space-y-0.5">
            {groups.length === 0 && (
              <li className="px-1.5 py-2 text-[11px] text-muted-foreground">Nothing to filter</li>
            )}
            {groups.map((group) => {
              const def = BFO_BUCKET_BY_TYPE[group.bucket] ?? BFO_BUCKET_BY_TYPE.Unknown;
              const typeHidden = hiddenTypes.has(group.label);
              const isExpanded = expanded.has(group.label);
              return (
                <li key={group.label}>
                  <div className="flex items-center gap-1">
                    <label className="flex min-w-0 flex-1 items-center gap-1.5 rounded px-1.5 py-1 text-[11px] hover:bg-workspace-accent-10">
                      <input
                        type="checkbox"
                        checked={!typeHidden}
                        onChange={() => onToggleType(group.label)}
                        className="h-3 w-3"
                      />
                      <i
                        className="inline-block h-2 w-2 flex-shrink-0 rounded-sm"
                        style={{ background: def.color, border: `1px solid ${def.border}` }}
                      />
                      <span className="truncate">{group.label}</span>
                      <span className="ml-auto flex-shrink-0 tabular-nums text-muted-foreground">
                        {group.instances.length}
                      </span>
                    </label>
                    <button
                      type="button"
                      disabled={group.instances.length === 0}
                      aria-expanded={isExpanded}
                      aria-label={`Show ${group.label} instances`}
                      onClick={() =>
                        setExpanded((prev) => {
                          const next = new Set(prev);
                          if (next.has(group.label)) next.delete(group.label);
                          else next.add(group.label);
                          return next;
                        })
                      }
                      className="rounded p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-40"
                    >
                      <ChevronDown size={11} className={cn('transition-transform', isExpanded && 'rotate-180')} />
                    </button>
                  </div>
                  {isExpanded && (
                    <ul className="ml-4 space-y-0.5 border-l pl-2">
                      {group.instances.map((instance) => (
                        <li key={instance.id}>
                          <label
                            className={cn(
                              'flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px] hover:bg-workspace-accent-10',
                              typeHidden && 'opacity-50',
                            )}
                          >
                            <input
                              type="checkbox"
                              disabled={typeHidden}
                              checked={!hiddenInstances.has(instance.id)}
                              onChange={() => onToggleInstance(instance.id)}
                              className="h-3 w-3"
                            />
                            <span className="truncate">{instance.label}</span>
                          </label>
                        </li>
                      ))}
                      {group.instances.length === 0 && (
                        <li className="px-1.5 py-0.5 text-[11px] text-muted-foreground">No instances</li>
                      )}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
          <div className="mt-1 flex gap-1 border-t pt-1">
            <button
              type="button"
              onClick={onSelectAll}
              className="flex-1 rounded px-2 py-1 text-[11px] hover:bg-workspace-accent-10 hover:text-workspace-accent"
            >
              Select all
            </button>
            <button
              type="button"
              onClick={onClearAll}
              className="flex-1 rounded px-2 py-1 text-[11px] hover:bg-workspace-accent-10 hover:text-workspace-accent"
            >
              Clear all
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Date slicer over the loaded window, the cockpit's `renderDateSlicer`.
 *
 * One track, two cursors. Two native range inputs are stacked on the same
 * track rather than drawn from scratch so both ends stay keyboard operable;
 * `.range-dual` in globals.css makes the inputs transparent to the pointer
 * except at their thumbs, which is what keeps the lower one grabbable.
 */
export function TemporalSlicer({
  range,
  start,
  end,
  onChange,
}: {
  range: { start: string; end: string } | null;
  start: string | null;
  end: string | null;
  onChange: (start: string | null, end: string | null) => void;
}) {
  const bounds = useMemo(() => {
    if (!range) return null;
    const min = new Date(range.start).getTime();
    const max = new Date(range.end).getTime();
    return Number.isNaN(min) || Number.isNaN(max) || max <= min ? null : { min, max };
  }, [range]);

  if (!bounds) {
    return (
      <div className="pointer-events-auto absolute inset-x-3 bottom-3 z-20 flex items-center gap-2 rounded-lg border bg-background/90 px-3 py-2 backdrop-blur">
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Temporal</span>
        <span className="text-[11px] text-muted-foreground">No range</span>
      </div>
    );
  }

  const span = bounds.max - bounds.min;
  const startValue = Math.min(start ? new Date(start).getTime() : bounds.min, end ? new Date(end).getTime() : bounds.max);
  const endValue = Math.max(startValue, end ? new Date(end).getTime() : bounds.max);
  const pct = (value: number) => ((value - bounds.min) / span) * 100;
  const sliced = Boolean(start || end);

  return (
    <div className="pointer-events-auto absolute inset-x-3 bottom-3 z-20 flex items-center gap-3 rounded-lg border bg-background/90 px-3 py-2 backdrop-blur">
      <span className="flex-shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground">
        Temporal
      </span>
      <span className="flex-shrink-0 font-mono text-[9px] leading-tight text-muted-foreground">
        {formatRangeBound(new Date(startValue).toISOString())}
      </span>

      <div className="relative h-4 min-w-0 flex-1">
        <span className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-muted" />
        <span
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-workspace-accent"
          style={{ left: `${pct(startValue)}%`, right: `${100 - pct(endValue)}%` }}
        />
        <input
          type="range"
          aria-label="Range start"
          min={bounds.min}
          max={bounds.max}
          step={1000}
          value={startValue}
          onChange={(e) => {
            const next = Math.min(Number(e.target.value), endValue);
            onChange(new Date(next).toISOString(), end);
          }}
          className="range-dual"
        />
        <input
          type="range"
          aria-label="Range end"
          min={bounds.min}
          max={bounds.max}
          step={1000}
          value={endValue}
          onChange={(e) => {
            const next = Math.max(Number(e.target.value), startValue);
            onChange(start, new Date(next).toISOString());
          }}
          className="range-dual"
        />
      </div>

      <span className="flex-shrink-0 font-mono text-[9px] leading-tight text-muted-foreground">
        {formatRangeBound(new Date(endValue).toISOString())}
      </span>
      <button
        type="button"
        disabled={!sliced}
        onClick={() => onChange(null, null)}
        className="flex-shrink-0 rounded border px-1.5 py-0.5 text-[10px] hover:bg-workspace-accent-10 hover:text-workspace-accent disabled:opacity-40"
      >
        Reset
      </button>
    </div>
  );
}

export function EventGraphToolbar({
  model,
  filters,
  onFiltersChange,
  searchValue,
  onSearchChange,
  onPickProcess,
  layout,
}: {
  model: EventGraphModel;
  filters: GraphFilters;
  onFiltersChange: (next: GraphFilters) => void;
  searchValue: string;
  onSearchChange: (value: string) => void;
  onPickProcess: (uri: string) => void;
  layout: string;
}) {
  const [suggestOpen, setSuggestOpen] = useState(false);
  const searchRef = useDismissOnOutside(suggestOpen, () => setSuggestOpen(false));

  const suggestions = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    if (query.length < SEARCH_MIN_CHARS) return null;
    return model.processInstances
      .filter((instance) => instance.label.toLowerCase().includes(query) || instance.type.toLowerCase().includes(query))
      .slice(0, 40);
  }, [model.processInstances, searchValue]);

  const patch = (next: Partial<GraphFilters>) => onFiltersChange({ ...filters, ...next });
  const toggleIn = (set: Set<string>, key: string) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  };

  return (
    <div
      className={cn(
        'pointer-events-auto absolute left-3 top-3 z-20 flex gap-2 rounded-lg border bg-background/90 p-2 backdrop-blur',
        layout === 'column' ? 'flex-col items-start' : 'flex-wrap items-center',
      )}
    >
      <div ref={searchRef} className="relative">
        <label className="flex items-center gap-1.5">
          <Search size={12} className="text-muted-foreground" />
          <input
            type="search"
            value={searchValue}
            onChange={(e) => {
              onSearchChange(e.target.value);
              setSuggestOpen(true);
            }}
            onFocus={() => setSuggestOpen(true)}
            placeholder="Search processes…"
            autoComplete="off"
            className="w-52 rounded border bg-transparent px-2 py-1 text-[11px]"
          />
        </label>
        {suggestOpen && (
          <ul className="absolute left-0 top-full z-30 mt-1 max-h-72 w-64 overflow-y-auto rounded-lg border bg-background p-1 shadow-lg">
            {suggestions === null && (
              <li className="px-2 py-1.5 text-[11px] text-muted-foreground">
                Type at least {SEARCH_MIN_CHARS} characters to search
              </li>
            )}
            {suggestions?.length === 0 && (
              <li className="px-2 py-1.5 text-[11px] text-muted-foreground">No matches</li>
            )}
            {suggestions?.map((instance) => (
              <li key={instance.id}>
                <button
                  type="button"
                  onClick={() => {
                    onPickProcess(instance.id);
                    setSuggestOpen(false);
                  }}
                  className="flex w-full flex-col items-start rounded px-2 py-1 text-left hover:bg-workspace-accent-10"
                >
                  <span className="text-[11px] font-medium">{instance.label}</span>
                  <span className="font-mono text-[9px] text-muted-foreground">{instance.type}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <FilterDropdown
        title="Processes"
        groups={model.processGroups}
        instances={model.processInstances}
        hiddenTypes={filters.hiddenProcessTypes}
        hiddenInstances={filters.hiddenProcessInstances}
        onToggleType={(label) => patch({ hiddenProcessTypes: toggleIn(filters.hiddenProcessTypes, label) })}
        onToggleInstance={(id) => patch({ hiddenProcessInstances: toggleIn(filters.hiddenProcessInstances, id) })}
        onSelectAll={() => patch({ hiddenProcessTypes: new Set(), hiddenProcessInstances: new Set() })}
        onClearAll={() =>
          patch({
            hiddenProcessTypes: new Set(model.processGroups.map((group) => group.label)),
            hiddenProcessInstances: new Set(model.processInstances.map((instance) => instance.id)),
          })
        }
      />

      <FilterDropdown
        title="Classes"
        groups={model.classGroups}
        instances={model.classInstances}
        hiddenTypes={filters.hiddenClassTypes}
        hiddenInstances={filters.hiddenClassInstances}
        onToggleType={(label) => patch({ hiddenClassTypes: toggleIn(filters.hiddenClassTypes, label) })}
        onToggleInstance={(id) => patch({ hiddenClassInstances: toggleIn(filters.hiddenClassInstances, id) })}
        onSelectAll={() => patch({ hiddenClassTypes: new Set(), hiddenClassInstances: new Set() })}
        onClearAll={() =>
          patch({
            hiddenClassTypes: new Set(model.classGroups.map((group) => group.label)),
            hiddenClassInstances: new Set(model.classInstances.map((instance) => instance.id)),
          })
        }
      />
    </div>
  );
}
