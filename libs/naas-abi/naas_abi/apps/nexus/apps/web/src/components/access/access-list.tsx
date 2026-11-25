'use client';

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, ChevronUp, Filter } from 'lucide-react';
import { SearchBox } from '@/components/settings/search-box';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { rowMatchesColumnFilter } from '@/components/settings/users-table/users-table-filter';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { countFacets } from '@/app/settings/lib/page-helpers';
import '@/app/organizations/[orgId]/settings/users/users.css';
import '@/app/organizations/[orgId]/settings/components/org-settings-components.css';
import '@/app/settings/users/users.css';
import './access-list.css';

/**
 * The list pages of Access (Policies, Groups, Service accounts) look like Platform › Users:
 * the page header holds the page's own action (Create …) beside Refresh, a search box sits
 * above a sortable table, a row opens its page, and a row's actions are icon buttons at its end.
 */

/** Where a list page puts its header action: a slot in the page header of its level. */
export const AccessHeaderSlotContext = createContext<HTMLElement | null>(null);

/** The page's own action, shown in the page header beside Refresh; above the list where the
 *  page has no header (a page shown alone). */
export function AccessHeaderAction({ children }: { children: ReactNode }) {
  const slot = useContext(AccessHeaderSlotContext);
  return slot ? createPortal(children, slot) : <div className="access-list-actions">{children}</div>;
}

/** The header slot a level's page header carries before its Refresh button. */
export function AccessHeaderSlot({ onSlot }: { onSlot: (slot: HTMLElement | null) => void }) {
  return <span ref={onSlot} className="access-header-slot" style={{ display: 'contents' }} />;
}

/** Where a list page tells its level whether it shows an instance's page (a policy's, a group's)
 *  rather than its list: the level's header is the list's, and goes with it. */
export const AccessInstanceContext = createContext<((open: boolean) => void) | null>(null);

/** Tells the level, before the screen is painted, whether an instance's page is shown: a click
 *  on a row opens it at once, before the address follows, and the list's header never shows
 *  above it. */
export function useAccessInstance(open: boolean) {
  const report = useContext(AccessInstanceContext);
  useLayoutEffect(() => {
    report?.(open);
  }, [report, open]);
}

/** Where a list page tells its level's header how many it lists (the badge by the title). */
export const AccessBadgeContext = createContext<((badge: string | null) => void) | null>(null);

/** The badge by the page title, as Users shows "149 users": ``n`` rows (``more``: a page of
 *  them, more to load), or nothing while the list is read. Cleared when the page goes. */
export function useAccessBadge(n: number | null, noun: string, plural = `${noun}s`, more = false) {
  const report = useContext(AccessBadgeContext);
  const badge = n === null ? null : `${n}${more ? '+' : ''} ${n === 1 && !more ? noun : plural}`;
  useEffect(() => {
    report?.(badge);
  }, [report, badge]);
  useEffect(() => () => report?.(null), [report]);
}

export type SortDir = 'asc' | 'desc';

export type ListColumn<T> = {
  id: string;
  label: string;
  /** What the column sorts by; a column without one does not sort. */
  sortBy?: (row: T) => string | number;
  /** The texts its filter offers and matches (as Users' column filters); none: no filter. */
  values?: (row: T) => string[];
  className?: string;
};

export type ColumnFilters = Record<string, ColumnFilterState | undefined>;

/** Search, column filters and sort over rows held in memory, as Platform › Users does.
 *  ``keepOrder``: no sorting (a tree's order is its own). */
export function useListControls<T>(
  rows: T[] | null,
  { searchText, columns, initialSort, keepOrder = false }: {
    searchText: (row: T) => (string | null | undefined)[];
    columns: ListColumn<T>[];
    initialSort?: string;
    keepOrder?: boolean;
  },
) {
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<ColumnFilters>({});
  const [sortKey, setSortKey] = useState<string | null>(initialSort ?? null);
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const filtering = columns.some((c) => c.values && !isBlank(filters[c.id]));
  const visible = useMemo(() => {
    const all = rows ?? [];
    const words = search.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const matched = all.filter((row) => {
      if (words.length) {
        const text = searchText(row).filter(Boolean).join(' ').toLowerCase();
        if (!words.every((word) => text.includes(word))) return false;
      }
      return columns.every((c) => !c.values || rowMatchesColumnFilter(c.values(row), filters[c.id]));
    });
    const column = keepOrder ? undefined : columns.find((c) => c.id === sortKey);
    if (!column?.sortBy) return matched;
    const sign = sortDir === 'asc' ? 1 : -1;
    const by = column.sortBy;
    return [...matched].sort((a, b) => {
      const x = by(a);
      const y = by(b);
      return sign * (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y)));
    });
    // searchText and columns are the page's own: read anew each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, search, filters, sortKey, sortDir, keepOrder]);
  const toggleSort = (id: string) => {
    if (sortKey === id) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(id);
      setSortDir('asc');
    }
  };
  const loadFacets = useCallback(
    async (columnId: string, query: string): Promise<FacetBucket[]> => {
      const column = columns.find((c) => c.id === columnId);
      if (!column?.values) return [];
      const needle = query.trim().toLowerCase();
      return countFacets((rows ?? []).flatMap((row) => column.values!(row))).filter((bucket) =>
        bucket.value.toLowerCase().includes(needle),
      );
    },
    // columns are the page's own: read anew each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows],
  );
  const clear = () => {
    setSearch('');
    setFilters({});
  };
  return {
    search,
    setSearch,
    filters,
    setFilters,
    loadFacets,
    visible,
    sortKey,
    sortDir,
    toggleSort,
    clear,
    filtered: search.trim() !== '' || filtering,
    /** What the rows shown are made of: a table paged over them goes back to its first page
     *  when it changes (`usePagedRows`). */
    pageKey: JSON.stringify([search, filters, sortKey, sortDir]),
  };
}

export type ListControls = Pick<
  ReturnType<typeof useListControls>,
  'filters' | 'setFilters' | 'loadFacets' | 'sortKey' | 'sortDir' | 'toggleSort'
>;

/** The search box, and once the search or a filter narrows the list, how many rows show
 *  and a way back to all, as on Users. */
export function ListSearch({
  value,
  onChange,
  placeholder,
  label,
  shown,
  total,
  noun,
  plural = `${noun}s`,
  filtered = value.trim() !== '',
  onClear = () => onChange(''),
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder: string;
  label: string;
  shown: number;
  total: number;
  noun: string;
  plural?: string;
  filtered?: boolean;
  onClear?: () => void;
}) {
  return (
    <>
      <SearchBox value={value} onChange={onChange} placeholder={placeholder} label={label} />
      {filtered && (
        <p className="org-settings-users-filter-meta">
          {shown} of {total} {total === 1 ? noun : plural}
          <button type="button" className="org-settings-users-filter-clear" onClick={onClear}>
            Clear search and filters
          </button>
        </p>
      )}
    </>
  );
}

/** A header row of sortable and filterable columns (Users' sort arrows and funnel), then
 *  the (unlabelled) actions column. */
export function ListHead<T>({
  columns,
  controls,
  actions = true,
}: {
  columns: ListColumn<T>[];
  controls: ListControls;
  actions?: boolean;
}) {
  const { filters, setFilters, loadFacets, sortKey, sortDir, toggleSort } = controls;
  const [open, setOpen] = useState<{ id: string; left: number; top: number } | null>(null);
  return (
    <thead>
      <tr>
        {columns.map((column) => {
          const active = !isBlank(filters[column.id]);
          return (
            <th key={column.id} className={column.className}>
              <div className="org-settings-users-th">
                {column.sortBy ? (
                  <button
                    type="button"
                    className="org-settings-users-sort"
                    data-sort={column.id}
                    onClick={() => toggleSort(column.id)}
                    title="Sort"
                  >
                    <span>{column.label}</span>
                    {sortKey === column.id && sortDir === 'asc' && <ChevronUp size={12} />}
                    {sortKey === column.id && sortDir === 'desc' && <ChevronDown size={12} />}
                  </button>
                ) : (
                  <span className="org-settings-users-sort">
                    <span>{column.label}</span>
                  </span>
                )}
                {column.values && (
                  <button
                    type="button"
                    className={`org-settings-users-filter${active ? ' is-active' : ''}`}
                    data-filter-trigger=""
                    title="Filter"
                    aria-label={`Filter ${column.label}`}
                    onClick={(event) => {
                      if (open?.id === column.id) {
                        setOpen(null);
                        return;
                      }
                      const rect = event.currentTarget.getBoundingClientRect();
                      setOpen({ id: column.id, left: rect.left, top: rect.bottom + 4 });
                    }}
                  >
                    <Filter size={11} />
                  </button>
                )}
              </div>
              {open?.id === column.id && (
                <ColumnFilterPopover
                  columnId={column.id}
                  label={column.label}
                  datatype="string"
                  facetable
                  anchor={{ left: open.left, top: open.top }}
                  state={filters[column.id]}
                  onChange={(next) => setFilters((current) => ({ ...current, [column.id]: next }))}
                  onClear={() =>
                    setFilters((current) => {
                      const next = { ...current };
                      delete next[column.id];
                      return next;
                    })
                  }
                  loadFacets={loadFacets}
                  onClose={() => setOpen(null)}
                />
              )}
            </th>
          );
        })}
        {actions && <th aria-label="Actions" />}
      </tr>
    </thead>
  );
}

/** The actions cell of a row, as Users lays it out: icon buttons at the row's end. */
export function RowActions({ children }: { children: ReactNode }) {
  return (
    <td className="platform-users-actions-cell">
      <span className="org-settings-users-row-actions platform-users-actions">{children}</span>
    </td>
  );
}

/** A row that opens its page on a click anywhere but its own buttons and fields. */
export function rowOpener(open: (() => void) | null) {
  return open
    ? {
        className: 'org-settings-users-row-link',
        onClick: (event: React.MouseEvent) => {
          if ((event.target as HTMLElement).closest('button, a, input, select, label, form, textarea')) return;
          open();
        },
      }
    : {};
}

/** A row's mark (its initial, round, as Users shows an avatar), then its name over its id,
 *  as Users shows a name over an email. */
export function NameCell({
  name,
  detail,
  badge,
  initial,
}: {
  name: ReactNode;
  detail?: ReactNode;
  badge?: ReactNode;
  /** The text the round mark takes its first letter from. */
  initial?: string;
}) {
  const letter = (initial ?? (typeof name === 'string' ? name : '')).trim().charAt(0).toUpperCase();
  return (
    <div className="org-settings-users-row-start">
      {letter ? <div className="org-settings-users-avatar" aria-hidden="true">{letter}</div> : null}
      <div className="org-settings-users-identity">
        <p className="org-settings-users-name">
          {name}
          {badge}
        </p>
        {detail ? <p className="org-settings-users-email">{detail}</p> : null}
      </div>
    </div>
  );
}
