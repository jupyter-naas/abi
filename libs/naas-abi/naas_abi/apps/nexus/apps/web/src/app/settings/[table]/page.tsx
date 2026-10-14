'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Download,
  Filter,
  Table2,
} from 'lucide-react';
import { authFetch } from '@/stores/auth';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { rowMatchesColumnFilter } from '@/app/organizations/[orgId]/settings/users/users-table-filter';
import {
  downloadTableExport,
  type UsersExportFormat,
} from '@/app/organizations/[orgId]/settings/users/users-table-export';
import {
  cellText,
  compareCells,
  NULL_LABEL,
  REDACTED_LABEL,
  type CellValue,
} from '../lib/table-cells';
import {
  platformRowId,
  platformRowPath,
  platformTableFromSlug,
  platformTableLabel,
} from '../lib/tables';
import { matchesSearch } from '../lib/search';
import { pageWindow, TABLE_PAGE_SIZE } from '../lib/pagination';
import { fetchTableSchema, SchemaTable, type SchemaState } from '../components/schema-table';
import { SearchBox } from '../components/search-box';
import '@/app/organizations/[orgId]/settings/users/users.css';

/** One table, as `GET /api/admin/tables/{name}` returns it. */
interface PlatformTable {
  name: string;
  description: string;
  columns: string[];
  rows: Record<string, CellValue>[];
  total: number;
  truncated: boolean;
  /** Columns that make up the row id; empty when rows cannot be opened. */
  primary_key?: string[];
}

type SortDir = 'asc' | 'desc';

function countFacets(values: string[]): FacetBucket[] {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count }));
}

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
  } catch {
    // ignore parse errors
  }
  return fallback;
}

function plural(count: number, word: string): string {
  return `${count} ${count === 1 ? word : `${word}s`}`;
}

/**
 * One table: every column and row, with sorting, per-column filters and
 * export. Secret columns arrive masked. Click a row to open its page.
 */
export default function PlatformTablePage() {
  const params = useParams<{ table: string }>();
  const slug = params?.table ?? '';
  const tableName = platformTableFromSlug(slug) ?? slug;
  const router = useRouter();
  const [table, setTable] = useState<PlatformTable | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const tableWrapRef = useRef<HTMLDivElement>(null);
  const [showSchema, setShowSchema] = useState(false);
  const [schema, setSchema] = useState<SchemaState | null>(null);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [columnFilters, setColumnFilters] = useState<Record<string, ColumnFilterState>>({});
  const [openFilter, setOpenFilter] = useState<{ id: string; left: number; top: number } | null>(
    null
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError('');
    setTable(null);
    setSortKey(null);
    setColumnFilters({});
    setOpenFilter(null);
    setSearch('');
    setShowSchema(false);
    setSchema(null);
    (async () => {
      try {
        const res = await authFetch(`/api/admin/tables/${encodeURIComponent(tableName)}`);
        if (cancelled) return;
        if (!res.ok) {
          setLoadError(
            res.status === 404
              ? await readApiError(res, 'This table is not available.')
              : await readApiError(res, `Failed to load ${tableName} (HTTP ${res.status}).`)
          );
          return;
        }
        setTable(await res.json());
      } catch {
        if (!cancelled) setLoadError(`Failed to load ${tableName}. Please try again.`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tableName]);

  const columns = useMemo(() => table?.columns ?? [], [table]);
  const rows = useMemo(() => table?.rows ?? [], [table]);

  const visibleRows = useMemo(() => {
    const filtered = rows.filter(
      (row) =>
        matchesSearch(
          columns.map((column) => cellText(row[column])),
          search
        ) &&
        columns.every((column) =>
          rowMatchesColumnFilter([cellText(row[column])], columnFilters[column])
        )
    );
    if (sortKey) {
      filtered.sort((a, b) => {
        const cmp = compareCells(a[sortKey], b[sortKey]);
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }
    return filtered;
  }, [rows, columns, search, columnFilters, sortKey, sortDir]);

  // A new search, filter or sort starts again from the first page.
  useEffect(() => {
    setPage(0);
  }, [table, search, columnFilters, sortKey, sortDir]);

  const pager = pageWindow(visibleRows.length, page);
  const pagedRows = visibleRows.slice(pager.start, pager.end);

  const goToPage = (next: number) => {
    setPage(next);
    tableWrapRef.current?.scrollTo({ top: 0 });
  };

  const loadFacets = useCallback(
    async (columnId: string, search: string): Promise<FacetBucket[]> => {
      const query = search.trim().toLowerCase();
      const values = rows.map((row) => cellText(row[columnId]));
      return countFacets(values).filter((bucket) => bucket.value.toLowerCase().includes(query));
    },
    [rows]
  );

  const toggleSort = (column: string) => {
    if (sortKey === column) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(column);
    setSortDir('asc');
  };

  const toggleSchema = async () => {
    const next = !showSchema;
    setShowSchema(next);
    if (!next || schema?.status === 'ready') return;
    setSchema({ status: 'loading' });
    setSchema(await fetchTableSchema(tableName));
  };

  const clearFilter = (column: string) =>
    setColumnFilters((current) => {
      const next = { ...current };
      delete next[column];
      return next;
    });

  const hasActiveFilters = columns.some((column) => !isBlank(columnFilters[column]));

  const exportVisibleRows = (format: UsersExportFormat) => {
    const date = new Date().toISOString().slice(0, 10);
    downloadTableExport(
      columns,
      visibleRows.map((row) => columns.map((column) => cellText(row[column]))),
      format,
      `${tableName}_${date}`,
      tableName
    );
  };

  return (
    <div className="org-settings-users-page platform-table-page">
      <div className="org-settings-users-main">
        <OrgSettingsPageHeader
          title={platformTableLabel(tableName)}
          badge={
            table
              ? `${tableName} · ${plural(table.total, 'row')} · ${plural(columns.length, 'column')}`
              : tableName
          }
          subtitle={table?.description ?? ''}
          actions={
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button
                  type="button"
                  className="org-settings-users-secondary-button"
                  disabled={visibleRows.length === 0}
                >
                  <Download size={16} />
                  Export
                  <ChevronDown size={14} />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="end"
                  sideOffset={4}
                  className="org-settings-users-export-menu"
                >
                  <DropdownMenu.Item
                    className="org-settings-users-export-item"
                    onSelect={() => exportVisibleRows('csv')}
                  >
                    CSV
                  </DropdownMenu.Item>
                  <DropdownMenu.Item
                    className="org-settings-users-export-item"
                    onSelect={() => exportVisibleRows('xlsx')}
                  >
                    Excel (.xlsx)
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          }
        />

        <div className="platform-table-schema-toggle-row">
          <button
            type="button"
            className="org-settings-users-secondary-button"
            onClick={() => void toggleSchema()}
            aria-expanded={showSchema}
          >
            {showSchema ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {showSchema ? 'Hide schema' : 'Show schema'}
          </button>
        </div>

        {showSchema && (
          <div className="platform-table-schema-panel">
            <SchemaTable state={schema ?? undefined} />
          </div>
        )}

        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search every column..."
          label={`Search ${tableName}`}
        />

        {loadError && (
          <div className="org-settings-users-alert" role="alert">
            <AlertCircle size={16} />
            <span>{loadError}</span>
          </div>
        )}

        {table?.truncated && (
          <p className="org-settings-users-filter-meta">
            Showing the first {rows.length} of {table.total} rows.
          </p>
        )}

        {(hasActiveFilters || search.trim()) && (
          <p className="org-settings-users-filter-meta">
            {visibleRows.length} of {plural(rows.length, 'row')}
            <button
              type="button"
              className="org-settings-users-filter-clear"
              onClick={() => {
                setSearch('');
                setColumnFilters({});
              }}
            >
              Clear search and filters
            </button>
          </p>
        )}

        <div className="org-settings-users-table-wrap" ref={tableWrapRef}>
          {loading ? (
            <div className="org-settings-loading">Loading {tableName}...</div>
          ) : !table ? null : rows.length === 0 ? (
            <div className="org-settings-empty">
              <div className="org-settings-empty-icon">
                <Table2 size={24} />
              </div>
              <p className="org-settings-empty-title">No rows</p>
              <p className="org-settings-empty-body">
                Columns: {columns.join(', ')}
              </p>
            </div>
          ) : (
            <table className="org-settings-users-table">
              <thead>
                <tr>
                  {columns.map((column) => {
                    const sorted = sortKey === column;
                    const active = !isBlank(columnFilters[column]);
                    return (
                      <th key={column}>
                        <div className="org-settings-users-th">
                          <button
                            type="button"
                            className="org-settings-users-sort"
                            onClick={() => toggleSort(column)}
                            title="Sort"
                          >
                            <span>{column}</span>
                            {sorted && sortDir === 'asc' && <ChevronUp size={12} />}
                            {sorted && sortDir === 'desc' && <ChevronDown size={12} />}
                          </button>
                          <button
                            type="button"
                            className={`org-settings-users-filter${active ? ' is-active' : ''}`}
                            data-filter-trigger=""
                            title="Filter"
                            onClick={(event) => {
                              if (openFilter?.id === column) {
                                setOpenFilter(null);
                                return;
                              }
                              const rect = event.currentTarget.getBoundingClientRect();
                              setOpenFilter({ id: column, left: rect.left, top: rect.bottom + 4 });
                            }}
                          >
                            <Filter size={11} />
                          </button>
                        </div>
                        {openFilter?.id === column && (
                          <ColumnFilterPopover
                            columnId={column}
                            label={column}
                            datatype="string"
                            facetable
                            anchor={{ left: openFilter.left, top: openFilter.top }}
                            state={columnFilters[column]}
                            onChange={(next) =>
                              setColumnFilters((current) => ({ ...current, [column]: next }))
                            }
                            onClear={() => clearFilter(column)}
                            loadFacets={loadFacets}
                            onClose={() => setOpenFilter(null)}
                          />
                        )}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {visibleRows.length === 0 && (
                  <tr>
                    <td colSpan={columns.length} className="org-settings-users-no-match">
                      No rows match the current search and filters
                    </td>
                  </tr>
                )}
                {pagedRows.map((row, index) => {
                  const id = platformRowId(row, table.primary_key ?? []);
                  const open = id === null ? undefined : () => router.push(platformRowPath(tableName, id));
                  return (
                  <tr
                    key={id ?? index}
                    className={open ? 'platform-table-row-link' : undefined}
                    onClick={open}
                    onKeyDown={(event) => {
                      if (open && event.key === 'Enter') open();
                    }}
                    tabIndex={open ? 0 : undefined}
                    role={open ? 'link' : undefined}
                  >
                    {columns.map((column) => {
                      const text = cellText(row[column]);
                      const className =
                        text === NULL_LABEL && row[column] === null
                          ? 'platform-table-cell-null'
                          : text === REDACTED_LABEL
                            ? 'platform-table-cell-redacted'
                            : undefined;
                      return (
                        <td key={column} className={className} title={text}>
                          {text}
                        </td>
                      );
                    })}
                  </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {visibleRows.length > TABLE_PAGE_SIZE && (
          <nav className="platform-table-pager" aria-label="Table pages">
            <span>
              Rows {(pager.start + 1).toLocaleString()}–{pager.end.toLocaleString()} of{' '}
              {visibleRows.length.toLocaleString()}
            </span>
            <span className="platform-table-pager-controls">
              <button
                type="button"
                className="org-settings-users-secondary-button"
                onClick={() => goToPage(pager.page - 1)}
                disabled={pager.page === 0}
                aria-label="Previous page"
              >
                <ChevronLeft size={14} />
                Previous
              </button>
              <span>
                Page {pager.page + 1} of {pager.pageCount}
              </span>
              <button
                type="button"
                className="org-settings-users-secondary-button"
                onClick={() => goToPage(pager.page + 1)}
                disabled={pager.page >= pager.pageCount - 1}
                aria-label="Next page"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </span>
          </nav>
        )}

        <p className="org-settings-footnote">
          Read-only view of the database table. Click a row to open it. Credentials (password
          and token hashes, sign-in tokens, API keys, secrets) are masked, and long values are
          cut at 2,000 characters.
        </p>
      </div>
    </div>
  );
}
