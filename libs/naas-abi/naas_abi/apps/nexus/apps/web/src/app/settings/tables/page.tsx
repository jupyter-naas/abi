'use client';

import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Download,
  Filter,
  Loader2,
} from 'lucide-react';
import {
  downloadJsonExport,
  downloadWorkbookExport,
} from '@/app/organizations/[orgId]/settings/users/users-table-export';
import { ColumnFilterPopover } from '@/components/graph/explore/ColumnFilterPopover';
import { isBlank, type ColumnFilterState } from '@/lib/graph-query/filters';
import type { FacetBucket } from '@/lib/graph-query/types';
import { rowMatchesColumnFilter } from '@/app/organizations/[orgId]/settings/users/users-table-filter';
import { authFetch } from '@/stores/auth';
import { OrgSettingsPageHeader } from '@/app/organizations/[orgId]/settings/components/org-settings-page-header';
import { matchesSearch } from '../lib/search';
import { fetchTableSchema, SchemaTable, type SchemaState } from '../components/schema-table';
import { SearchBox } from '@/components/settings/search-box';
import {
  buildJsonExport,
  buildWorkbookSheets,
  mapWithLimit,
  type ExportedTable,
} from '../lib/export-all';
import { platformTablePath, type PlatformTableSummary } from '../lib/tables';
import { useTablesView, type TablesColumnId as ColumnId } from '../lib/tables-view';
import '@/app/organizations/[orgId]/settings/users/users.css';

async function readApiError(response: Response, fallback: string): Promise<string> {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
  } catch {
    // ignore parse errors
  }
  return fallback;
}

function formatCount(value: number | null): string {
  return value === null ? '—' : value.toLocaleString();
}

const COLUMNS: { id: ColumnId; label: string; numeric?: boolean }[] = [
  { id: 'table', label: 'Table' },
  { id: 'section', label: 'Section' },
  { id: 'description', label: 'Description' },
  { id: 'rows', label: 'Rows', numeric: true },
  { id: 'columns', label: 'Columns', numeric: true },
];

/** One row of the page: a registered table and its counts (null when missing here). */
type DashboardRow = PlatformTableSummary;

/** Filter values of a cell: the table filters on its name and its raw name. */
function cellValues(row: DashboardRow, columnId: ColumnId): string[] {
  if (columnId === 'table') return [row.label, row.name];
  if (columnId === 'section') return [row.section];
  if (columnId === 'description') return [row.description];
  const value = row[columnId];
  return [value === null ? '—' : String(value)];
}

function compareRows(a: DashboardRow, b: DashboardRow, columnId: ColumnId): number {
  if (columnId === 'rows' || columnId === 'columns') {
    return (a[columnId] ?? -1) - (b[columnId] ?? -1);
  }
  if (columnId === 'table') return a.label.localeCompare(b.label);
  return a[columnId].localeCompare(b[columnId]);
}

function countFacets(values: string[]): FacetBucket[] {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  return [...counts.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count }));
}

/**
 * Nexus tables: every table of the Nexus database, as the API's registry lists them,
 * with its section, row and column counts, sortable and filterable per column. Click
 * a table to open it; its chevron shows the schema here. Search, filters and sort stay
 * as they were when a table is closed.
 */
export default function NexusTablesPage() {
  const router = useRouter();
  const [summaries, setSummaries] = useState<PlatformTableSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [schemas, setSchemas] = useState<Record<string, SchemaState>>({});
  const [exporting, setExporting] = useState<{ done: number; total: number } | null>(null);
  const [exportError, setExportError] = useState('');
  const {
    search,
    setSearch,
    columnFilters,
    setColumnFilters,
    sortKey,
    sortDir,
    setSort,
    openTable,
    setOpenTable,
  } = useTablesView();
  const [openFilter, setOpenFilter] = useState<{ id: ColumnId; left: number; top: number } | null>(
    null
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch('/api/admin/tables');
        if (cancelled) return;
        if (!res.ok) {
          setLoadError(await readApiError(res, `Failed to load tables (HTTP ${res.status}).`));
          return;
        }
        setSummaries(await res.json());
      } catch {
        if (!cancelled) setLoadError('Failed to load tables. Please try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Registry order (by section) until a column is sorted.
  const dashboardRows: DashboardRow[] = summaries;

  const visibleRows = useMemo(() => {
    const rows = dashboardRows.filter((row) =>
      matchesSearch([row.label, row.name, row.section, row.description], search) &&
        COLUMNS.every((column) =>
        rowMatchesColumnFilter(cellValues(row, column.id), columnFilters[column.id])
      )
    );
    if (sortKey) {
      rows.sort((a, b) => {
        const cmp = compareRows(a, b, sortKey);
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }
    return rows;
  }, [dashboardRows, search, columnFilters, sortKey, sortDir]);

  const loadFacets = useCallback(
    async (columnId: string, search: string): Promise<FacetBucket[]> => {
      const query = search.trim().toLowerCase();
      const values = dashboardRows.map((row) => cellValues(row, columnId as ColumnId)[0]);
      return countFacets(values).filter((bucket) => bucket.value.toLowerCase().includes(query));
    },
    [dashboardRows]
  );

  const toggleSort = (columnId: ColumnId) => {
    if (sortKey === columnId) {
      setSort(columnId, sortDir === 'asc' ? 'desc' : 'asc');
      return;
    }
    setSort(columnId, columnId === 'rows' || columnId === 'columns' ? 'desc' : 'asc');
  };

  const clearFilter = (columnId: ColumnId) =>
    setColumnFilters((current) => {
      const next = { ...current };
      delete next[columnId];
      return next;
    });

  const hasActiveFilters = COLUMNS.some((column) => !isBlank(columnFilters[column.id]));

  const totals = useMemo(
    () => ({
      tables: summaries.length,
      rows: summaries.reduce((sum, summary) => sum + (summary.rows ?? 0), 0),
    }),
    [summaries]
  );

  /** Fetches every table (masked, as the table pages show them) and downloads one file. */
  const exportAllTables = async (format: 'json' | 'xlsx') => {
    if (exporting) return;
    setExportError('');
    // The tables this database has (a table missing here has no counts).
    const names = summaries.filter((summary) => summary.rows !== null).map((summary) => summary.name);
    setExporting({ done: 0, total: names.length });
    try {
      const tables = await mapWithLimit(names, 4, async (name) => {
        const res = await authFetch(`/api/admin/tables/${encodeURIComponent(name)}`);
        if (!res.ok) {
          throw new Error(await readApiError(res, `Failed to export ${name} (HTTP ${res.status}).`));
        }
        const table: ExportedTable = await res.json();
        setExporting((current) => (current ? { ...current, done: current.done + 1 } : current));
        return table;
      });
      const now = new Date();
      const basename = `nexus_tables_${now.toISOString().slice(0, 10)}`;
      if (format === 'json') downloadJsonExport(buildJsonExport(tables, now), basename);
      else downloadWorkbookExport(buildWorkbookSheets(tables), basename);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : 'Failed to export the tables.');
    } finally {
      setExporting(null);
    }
  };

  const loadSchema = useCallback(async (name: string) => {
    setSchemas((current) => ({ ...current, [name]: { status: 'loading' } }));
    const state = await fetchTableSchema(name);
    setSchemas((current) => ({ ...current, [name]: state }));
  }, []);

  const toggleSchema = async (name: string) => {
    if (openTable === name) {
      setOpenTable(null);
      return;
    }
    setOpenTable(name);
    if (schemas[name]?.status === 'ready') return;
    await loadSchema(name);
  };

  // Back from a table with a schema open: show it again.
  useEffect(() => {
    if (openTable) void loadSchema(openTable);
    // Once, for the schema the page was left with.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="org-settings-users-page platform-dashboard-page">
      <div className="org-settings-users-main">
        <OrgSettingsPageHeader
          title="Nexus tables"
          badge={
            loading
              ? undefined
              : `${totals.tables} ${totals.tables === 1 ? 'table' : 'tables'} · ${totals.rows.toLocaleString()} rows`
          }
          subtitle="Every table in the Nexus database. Search, sort and filter any column; click a table to open it, or its arrow to see its schema."
          actions={
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button
                  type="button"
                  className="org-settings-users-secondary-button"
                  disabled={loading || exporting !== null}
                >
                  {exporting ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Download size={16} />
                  )}
                  {exporting ? `Exporting ${exporting.done}/${exporting.total}` : 'Export'}
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
                    onSelect={() => void exportAllTables('json')}
                  >
                    JSON
                  </DropdownMenu.Item>
                  <DropdownMenu.Item
                    className="org-settings-users-export-item"
                    onSelect={() => void exportAllTables('xlsx')}
                  >
                    Excel (.xlsx), one sheet per table
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
          }
        />

        <SearchBox
          value={search}
          onChange={setSearch}
          placeholder="Search tables, sections and descriptions..."
          label="Search tables"
        />

        {(loadError || exportError) && (
          <div className="org-settings-users-alert" role="alert">
            <AlertCircle size={16} />
            <span>{loadError || exportError}</span>
          </div>
        )}

        {(hasActiveFilters || search.trim()) && (
          <p className="org-settings-users-filter-meta">
            {visibleRows.length} of {dashboardRows.length} tables
            <button
              type="button"
              className="org-settings-users-filter-clear"
              onClick={() => {
                setSearch('');
                setColumnFilters(() => ({}));
              }}
            >
              Clear search and filters
            </button>
          </p>
        )}

        <div className="org-settings-users-table-wrap">
          {loading ? (
            <div className="org-settings-loading">Loading tables...</div>
          ) : (
            <table className="org-settings-users-table">
              <thead>
                <tr>
                  {COLUMNS.map((column) => {
                    const sorted = sortKey === column.id;
                    const active = !isBlank(columnFilters[column.id]);
                    return (
                      <th key={column.id}>
                        <div
                          className={`org-settings-users-th${column.numeric ? ' platform-dashboard-th-numeric' : ''}`}
                        >
                          <button
                            type="button"
                            className="org-settings-users-sort"
                            onClick={() => toggleSort(column.id)}
                            title="Sort"
                          >
                            <span>{column.label}</span>
                            {sorted && sortDir === 'asc' && <ChevronUp size={12} />}
                            {sorted && sortDir === 'desc' && <ChevronDown size={12} />}
                          </button>
                          <button
                            type="button"
                            className={`org-settings-users-filter${active ? ' is-active' : ''}`}
                            data-filter-trigger=""
                            title="Filter"
                            onClick={(event) => {
                              if (openFilter?.id === column.id) {
                                setOpenFilter(null);
                                return;
                              }
                              const rect = event.currentTarget.getBoundingClientRect();
                              setOpenFilter({ id: column.id, left: rect.left, top: rect.bottom + 4 });
                            }}
                          >
                            <Filter size={11} />
                          </button>
                        </div>
                        {openFilter?.id === column.id && (
                          <ColumnFilterPopover
                            columnId={column.id}
                            label={column.label}
                            datatype="string"
                            facetable
                            anchor={{ left: openFilter.left, top: openFilter.top }}
                            state={columnFilters[column.id]}
                            onChange={(next) =>
                              setColumnFilters((current) => ({ ...current, [column.id]: next }))
                            }
                            onClear={() => clearFilter(column.id)}
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
                    <td colSpan={COLUMNS.length} className="org-settings-users-no-match">
                      No tables match the current search and filters
                    </td>
                  </tr>
                )}
                {visibleRows.map((row) => {
                  const isOpen = openTable === row.name;
                  return (
                    <Fragment key={row.name}>
                      <tr
                        className={`platform-dashboard-row${isOpen ? ' is-open' : ''}`}
                        onClick={() => router.push(platformTablePath(row.name))}
                      >
                        <td>
                          <span className="platform-dashboard-name">
                            <button
                              type="button"
                              className="platform-dashboard-schema-toggle"
                              aria-expanded={isOpen}
                              aria-label={isOpen ? `Hide the schema of ${row.name}` : `Show the schema of ${row.name}`}
                              title={isOpen ? 'Hide schema' : 'Show schema'}
                              onClick={(event) => {
                                event.stopPropagation();
                                void toggleSchema(row.name);
                              }}
                            >
                              {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                            </button>
                            <span>
                              <Link
                                href={platformTablePath(row.name)}
                                className="platform-dashboard-link"
                                onClick={(event) => event.stopPropagation()}
                              >
                                {row.label}
                              </Link>
                              <span className="platform-dashboard-raw">{row.name}</span>
                            </span>
                          </span>
                        </td>
                        <td className="platform-dashboard-description">{row.section}</td>
                        <td className="platform-dashboard-description">{row.description}</td>
                        <td className="platform-dashboard-number">{formatCount(row.rows)}</td>
                        <td className="platform-dashboard-number">{formatCount(row.columns)}</td>
                      </tr>
                      {isOpen && (
                        <tr className="platform-dashboard-schema">
                          <td colSpan={COLUMNS.length}>
                            <SchemaTable state={schemas[row.name]} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
