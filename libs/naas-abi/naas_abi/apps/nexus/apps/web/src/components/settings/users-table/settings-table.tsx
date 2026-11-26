'use client';

/**
 * The table of Settings › Users for any settings list: a search over every row, columns that sort
 * and filter (Excel-like, with the values found as facets), pages. `useSettingsTable` holds the
 * state and answers the rows to show; `SettingsTableHead` draws the header cells; the page keeps
 * its own rows and cells. Styles: `org-settings-users-*` (`users.css`, imported here).
 */
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, Filter } from 'lucide-react';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { matchesSearch } from '@/app/settings/lib/search';
import { countFacets } from '@/app/settings/lib/page-helpers';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { rowMatchesColumnFilter } from './users-table-filter';
import { usePagedRows, type PagedRows } from './table-pager';
import '@/app/organizations/[orgId]/settings/users/users.css';

export type SortDir = 'asc' | 'desc';
export type SettingsColumn<C extends string> = {
  id: C;
  label: string;
  /** Sorted and filtered; false for a column of actions or one with nothing to compare. */
  sortable?: boolean;
  className?: string;
};

export type SettingsTable<T, C extends string> = {
  search: string;
  setSearch: (value: string) => void;
  filters: Partial<Record<C, ColumnFilterState>>;
  setFilter: (column: C, state: ColumnFilterState | null) => void;
  sortKey: C;
  sortDir: SortDir;
  toggleSort: (column: C) => void;
  /** Every row the search and the filters keep, sorted. */
  shown: T[];
  /** The page of them shown. */
  paged: PagedRows<T>;
  /** A search or a filter is on. */
  narrowed: boolean;
  clear: () => void;
  loadFacets: (columnId: string, query: string) => Promise<FacetBucket[]>;
  columns: SettingsColumn<C>[];
};

/** Compares two cell texts as people read them: numbers in order, case ignored. */
export function compareCells(a: string, b: string): number {
  return a.localeCompare(b, undefined, { sensitivity: 'base', numeric: true });
}

export function useSettingsTable<T, C extends string>({
  rows,
  columns,
  cellValues,
  searchTexts,
  sortValue,
  initialSort,
  initialSearch = '',
  initialFilters = {},
}: {
  rows: readonly T[];
  columns: SettingsColumn<C>[];
  /** The values a column filter sees of a row (each one a facet). */
  cellValues: (row: T, column: C) => string[];
  /** What the search bar reads of a row. */
  searchTexts: (row: T) => readonly string[];
  /** What a column sorts on; its cell values joined by default. */
  sortValue?: (row: T, column: C) => string | number;
  initialSort: C;
  /** The search and the filters the table opens with (read once). */
  initialSearch?: string;
  initialFilters?: Partial<Record<C, ColumnFilterState>>;
}): SettingsTable<T, C> {
  const [search, setSearch] = useState(initialSearch);
  const [filters, setFilters] = useState<Partial<Record<C, ColumnFilterState>>>(initialFilters);
  const [sortKey, setSortKey] = useState<C>(initialSort);
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const shown = useMemo(() => {
    const kept = rows.filter(
      (row) =>
        matchesSearch(searchTexts(row), search) &&
        columns.every((column) => rowMatchesColumnFilter(cellValues(row, column.id), filters[column.id]))
    );
    const key = (row: T) => (sortValue ? sortValue(row, sortKey) : cellValues(row, sortKey).join(', '));
    const sign = sortDir === 'asc' ? 1 : -1;
    return kept
      .map((row, index) => ({ row, index, key: key(row) }))
      .sort((a, b) => {
        const order =
          typeof a.key === 'number' && typeof b.key === 'number'
            ? a.key - b.key
            : compareCells(String(a.key), String(b.key));
        return sign * order || a.index - b.index;
      })
      .map(({ row }) => row);
    // The callers' functions are pure readers of a row: the rows, the columns and the state decide.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, columns, search, filters, sortKey, sortDir]);

  const paged = usePagedRows(shown, JSON.stringify([search, filters, sortKey, sortDir]));
  const loadFacets = useCallback(
    async (columnId: string, query: string): Promise<FacetBucket[]> => {
      const needle = query.trim().toLowerCase();
      return countFacets(rows.flatMap((row) => cellValues(row, columnId as C))).filter((bucket) =>
        bucket.value.toLowerCase().includes(needle)
      );
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows]
  );

  return {
    search,
    setSearch,
    filters,
    setFilter: (column, state) =>
      setFilters((current) => {
        const next = { ...current };
        if (state) next[column] = state;
        else delete next[column];
        return next;
      }),
    sortKey,
    sortDir,
    toggleSort: (column) => {
      if (sortKey === column) {
        setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'));
        return;
      }
      setSortKey(column);
      setSortDir('asc');
    },
    shown,
    paged,
    narrowed: search.trim() !== '' || columns.some((column) => !isBlank(filters[column.id])),
    clear: () => {
      setSearch('');
      setFilters({});
    },
    loadFacets,
    columns,
  };
}

/** The header row of a settings table: each sortable column sorts on a click and filters from its
 *  funnel; `trailing` adds header cells after them (an Actions column). */
export function SettingsTableHead<T, C extends string>({
  table,
  trailing,
}: {
  table: SettingsTable<T, C>;
  trailing?: ReactNode;
}) {
  const [open, setOpen] = useState<{ id: C; left: number; top: number } | null>(null);
  return (
    <thead>
      <tr>
        {table.columns.map((column) => {
          if (column.sortable === false) {
            return (
              <th key={column.id} className={column.className}>
                {column.label}
              </th>
            );
          }
          const sorted = table.sortKey === column.id;
          const active = !isBlank(table.filters[column.id]);
          return (
            <th key={column.id} className={column.className}>
              <div className="org-settings-users-th">
                <button
                  type="button"
                  className="org-settings-users-sort"
                  data-sort={column.id}
                  onClick={() => table.toggleSort(column.id)}
                  title="Sort"
                >
                  <span>{column.label}</span>
                  {sorted && table.sortDir === 'asc' && <ChevronUp size={12} />}
                  {sorted && table.sortDir === 'desc' && <ChevronDown size={12} />}
                </button>
                <button
                  type="button"
                  className={`org-settings-users-filter${active ? ' is-active' : ''}`}
                  data-filter-trigger={column.id}
                  title="Filter"
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
              </div>
              {open?.id === column.id && (
                <ColumnFilterPopover
                  columnId={column.id}
                  label={column.label}
                  datatype="string"
                  facetable
                  anchor={{ left: open.left, top: open.top }}
                  state={table.filters[column.id]}
                  onChange={(next) => table.setFilter(column.id, next)}
                  onClear={() => table.setFilter(column.id, null)}
                  loadFacets={table.loadFacets}
                  onClose={() => setOpen(null)}
                />
              )}
            </th>
          );
        })}
        {trailing}
      </tr>
    </thead>
  );
}

/** "Clear search and filters", shown while either is on. */
export function SettingsTableClear<T, C extends string>({ table }: { table: SettingsTable<T, C> }) {
  if (!table.narrowed) return null;
  return (
    <button
      type="button"
      className="org-settings-users-filter-clear ml-3"
      data-action="clear-filters"
      onClick={table.clear}
    >
      Clear search and filters
    </button>
  );
}

/** The row under the header when nothing matches. */
export function SettingsTableNoMatch({ colSpan, noun }: { colSpan: number; noun: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="org-settings-users-no-match">
        No {noun} match the current search and filters
      </td>
    </tr>
  );
}
