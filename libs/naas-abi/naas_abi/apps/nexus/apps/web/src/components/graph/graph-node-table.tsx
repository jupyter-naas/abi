'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  ListFilter,
  Search,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ─── Public types ────────────────────────────────────────────────────────────

export interface ApiNodeInstance {
  uri: string;
  label: string;
  properties: Record<string, string>; // propUri → value
}

export interface ApiRelationTableRow {
  relation_label: string;
  domain_uri: string;
  domain_label: string;
  domain_properties: Record<string, string>;
  range_uri: string;
  range_label: string;
  range_properties: Record<string, string>;
}

// ─── Component props ─────────────────────────────────────────────────────────

interface GraphNodeTableProps {
  mode: 'single' | 'dual';
  // Single node mode
  classLabel?: string;
  instances?: ApiNodeInstance[];
  // Dual node mode (2 nodes selected with a relation)
  domainClassLabel?: string;
  rangeClassLabel?: string;
  relationRows?: ApiRelationTableRow[];
  // Extra selected property URIs (beyond uri/label) per class
  domainSelectedPropUris?: string[];
  rangeSelectedPropUris?: string[];
}

// ─── Internal types ───────────────────────────────────────────────────────────

interface ColDef {
  key: string;
  label: string;
  align: 'left' | 'right';
}

interface RowData {
  id: string;
  cells: Record<string, string>;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function uriFragment(uri: string): string {
  if (!uri) return '';
  for (const sep of ['#', '/']) {
    if (uri.includes(sep)) {
      const tail = uri.split(sep).pop();
      if (tail) return tail;
    }
  }
  return uri;
}

const PAGE_SIZES = [20, 50, 100] as const;
type PageSize = (typeof PAGE_SIZES)[number];
type SortDir = 'asc' | 'desc';

// ─── FilterDropdown ───────────────────────────────────────────────────────────

function FilterDropdown({
  availableValues,
  selectedValues,
  onChange,
  onClose,
  anchorRef,
}: {
  availableValues: string[];
  selectedValues: string[] | undefined;
  onChange: (vals: string[] | undefined) => void;
  onClose: () => void;
  anchorRef: React.MutableRefObject<HTMLButtonElement | null>;
}) {
  const dropRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState('');
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    if (anchorRef.current) {
      const rect = anchorRef.current.getBoundingClientRect();
      const left = Math.max(4, rect.right + window.scrollX - 208);
      setPos({ top: rect.bottom + window.scrollY + 2, left });
    }
    inputRef.current?.focus();
  }, [anchorRef]);

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (
        dropRef.current && !dropRef.current.contains(e.target as Node) &&
        anchorRef.current && !anchorRef.current.contains(e.target as Node)
      ) onClose();
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [onClose, anchorRef]);

  const displayed = search
    ? availableValues.filter((v) => v.toLowerCase().includes(search.toLowerCase()))
    : availableValues;

  const isChecked = (val: string) =>
    selectedValues === undefined || selectedValues.includes(val);

  const allChecked =
    selectedValues === undefined ||
    availableValues.every((v) => selectedValues.includes(v));
  const someChecked =
    !allChecked && availableValues.some((v) => isChecked(v));

  function toggleValue(val: string) {
    let next: string[];
    if (selectedValues === undefined) {
      next = availableValues.filter((v) => v !== val);
    } else {
      next = isChecked(val)
        ? selectedValues.filter((v) => v !== val)
        : [...selectedValues, val];
    }
    onChange(next.length === availableValues.length ? undefined : next);
  }

  function toggleAll() {
    onChange(allChecked ? [] : undefined);
  }

  if (!pos) return null;

  return createPortal(
    <div
      ref={dropRef}
      style={{ position: 'absolute', top: pos.top, left: pos.left, zIndex: 9999 }}
      className="w-52 rounded border border-border bg-popover shadow-xl flex flex-col max-h-72"
    >
      {/* Search */}
      <div className="flex items-center gap-1.5 border-b border-border px-2 py-1.5 shrink-0">
        <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <input
          ref={inputRef}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search values…"
          className="flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
          onKeyDown={(e) => e.key === 'Escape' && onClose()}
        />
        {search && (
          <button onClick={() => setSearch('')} className="text-muted-foreground hover:text-foreground">
            <X className="h-3 w-3" />
          </button>
        )}
      </div>

      {/* Select All */}
      {!search && (
        <label className="flex cursor-pointer items-center gap-2 border-b border-border px-2 py-1.5 text-xs font-medium hover:bg-muted/40 shrink-0">
          <input
            type="checkbox"
            checked={allChecked}
            ref={(el) => { if (el) el.indeterminate = someChecked; }}
            onChange={toggleAll}
            className="h-3.5 w-3.5 cursor-pointer accent-workspace-accent"
          />
          (Select All)
        </label>
      )}

      {/* Value list */}
      <div className="overflow-y-auto">
        {displayed.length === 0 ? (
          <p className="px-2 py-3 text-center text-xs text-muted-foreground">No values</p>
        ) : (
          displayed.map((val) => (
            <label
              key={val}
              className="flex cursor-pointer items-center gap-2 px-2 py-1 text-xs hover:bg-muted/40"
            >
              <input
                type="checkbox"
                checked={isChecked(val)}
                onChange={() => toggleValue(val)}
                className="h-3.5 w-3.5 cursor-pointer accent-workspace-accent"
              />
              <span className="truncate">{val}</span>
            </label>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-border px-2 py-1 shrink-0">
        <span className="text-[10px] text-muted-foreground">
          {selectedValues === undefined
            ? 'All selected'
            : `${selectedValues.length} / ${availableValues.length}`}
        </span>
        <button
          onClick={onClose}
          className="rounded bg-workspace-accent px-2 py-0.5 text-[10px] font-medium text-white hover:opacity-80"
        >
          OK
        </button>
      </div>
    </div>,
    document.body,
  );
}

// ─── Inner table renderer ─────────────────────────────────────────────────────

function DataTable({ columns, rows }: { columns: ColDef[]; rows: RowData[] }) {
  const [sortKey, setSortKey] = useState<string>(columns[0]?.key ?? '');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [filters, setFilters] = useState<Record<string, string[]>>({});
  const [openFilter, setOpenFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(20);

  const filterBtnRefs = useRef<Record<string, React.MutableRefObject<HTMLButtonElement | null>>>({});
  for (const col of columns) {
    if (!filterBtnRefs.current[col.key]) {
      filterBtnRefs.current[col.key] = { current: null };
    }
  }

  function toggleSort(key: string) {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('asc'); }
    setPage(1);
  }

  function applyFilter(col: string, vals: string[] | undefined) {
    setFilters((prev) => {
      const next = { ...prev };
      if (vals === undefined) delete next[col];
      else next[col] = vals;
      return next;
    });
    setPage(1);
  }

  function clearAllFilters() {
    setFilters({});
    setPage(1);
  }

  // Filter rows
  const filtered = useMemo(() => {
    const entries = Object.entries(filters);
    if (entries.length === 0) return rows;
    return rows.filter((r) =>
      entries.every(([col, vals]) => vals.includes(r.cells[col] ?? ''))
    );
  }, [rows, filters]);

  // Sort rows
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a.cells[sortKey] ?? '';
      const bv = b.cells[sortKey] ?? '';
      const cmp = av.localeCompare(bv);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  // Dropdown values for the open filter column (excluding its own filter)
  const dropdownValues = useMemo((): string[] => {
    if (!openFilter) return [];
    const entries = Object.entries(filters);
    const rowsExcept = rows.filter((r) =>
      entries.every(([col, vals]) => col === openFilter || vals.includes(r.cells[col] ?? ''))
    );
    const vals = rowsExcept.map((r) => r.cells[openFilter] ?? '');
    return [...new Set(vals)].sort((a, b) => a.localeCompare(b));
  }, [openFilter, rows, filters]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const pageRows = sorted.slice(pageStart, pageStart + pageSize);

  const hasFilters = Object.keys(filters).length > 0;

  return (
    <div className="flex flex-col gap-2">
      {hasFilters && (
        <div className="flex items-center gap-2 rounded border border-amber-200 bg-amber-50/70 dark:border-amber-800 dark:bg-amber-950/20 px-3 py-1.5 text-xs text-muted-foreground">
          <ListFilter className="h-3 w-3 shrink-0" />
          <span>{sorted.length} of {rows.length.toLocaleString()} row(s) shown</span>
          <button onClick={clearAllFilters} className="ml-auto underline hover:text-foreground">
            Clear all filters
          </button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="bg-workspace-accent-10 text-muted-foreground">
              {columns.map(({ key, label, align }) => {
                const isActiveSort = sortKey === key;
                const isActiveFilter = key in filters;
                return (
                  <th key={key} className="border border-border px-0 py-0 text-left">
                    <div className="flex items-stretch">
                      <button
                        onClick={() => toggleSort(key)}
                        className={cn(
                          'flex flex-1 items-center gap-1 px-2 py-2 font-semibold uppercase tracking-wide select-none transition-colors hover:bg-workspace-accent-10',
                          align === 'right' ? 'justify-end' : 'justify-start',
                          isActiveSort && 'text-foreground',
                        )}
                      >
                        {label}
                        {isActiveSort && (
                          sortDir === 'asc'
                            ? <ArrowUp className="h-3 w-3 shrink-0" />
                            : <ArrowDown className="h-3 w-3 shrink-0" />
                        )}
                      </button>
                      <button
                        ref={(el) => {
                          const ref = filterBtnRefs.current[key];
                          if (ref) ref.current = el;
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenFilter((prev) => (prev === key ? null : key));
                        }}
                        className={cn(
                          'flex shrink-0 items-center border-l border-border px-1.5 py-2 transition-colors hover:bg-workspace-accent-10',
                          isActiveFilter
                            ? 'text-workspace-accent bg-workspace-accent/5'
                            : 'text-muted-foreground hover:text-foreground',
                        )}
                        title={isActiveFilter ? `Filter active (${(filters[key] ?? []).length} value(s))` : 'Filter'}
                      >
                        <ListFilter className={cn('h-3 w-3', isActiveFilter && 'fill-workspace-accent/20')} />
                      </button>
                      {openFilter === key && (
                        <FilterDropdown
                          availableValues={dropdownValues}
                          selectedValues={filters[key]}
                          onChange={(vals) => applyFilter(key, vals)}
                          onClose={() => setOpenFilter(null)}
                          anchorRef={filterBtnRefs.current[key]}
                        />
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row) => (
              <tr
                key={row.id}
                className="bg-white hover:bg-muted/20 dark:bg-background dark:hover:bg-muted/20 transition-colors"
              >
                {columns.map(({ key, align }) => (
                  <td
                    key={key}
                    className={cn(
                      'border border-border px-2 py-1.5 max-w-[240px] truncate',
                      align === 'right' && 'text-right tabular-nums',
                    )}
                    title={row.cells[key] ?? ''}
                  >
                    {row.cells[key] || <span className="text-muted-foreground">—</span>}
                  </td>
                ))}
              </tr>
            ))}

            {pageRows.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length}
                  className="border border-border px-5 py-10 text-center text-sm text-muted-foreground"
                >
                  No rows match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination footer */}
      <div className="flex items-center justify-between gap-4 pt-1 text-xs text-muted-foreground">
        <span>
          {sorted.length === 0
            ? 'No results'
            : `${pageStart + 1}–${Math.min(pageStart + pageSize, sorted.length)} of ${sorted.length.toLocaleString()} row(s)`}
        </span>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span>Rows:</span>
            <div className="flex items-center gap-0.5">
              {PAGE_SIZES.map((size) => (
                <button
                  key={size}
                  onClick={() => { setPageSize(size); setPage(1); }}
                  className={cn(
                    'rounded px-2 py-0.5 text-xs transition-colors',
                    pageSize === size
                      ? 'bg-workspace-accent text-white font-semibold'
                      : 'hover:bg-muted',
                  )}
                >
                  {size}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePage === 1}
              className="rounded p-0.5 hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span className="tabular-nums">{safePage} / {totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage === totalPages}
              className="rounded p-0.5 hover:bg-muted disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main export ─────────────────────────────────────────────────────────────

export function GraphNodeTable({
  mode,
  classLabel,
  instances,
  domainClassLabel,
  rangeClassLabel,
  relationRows,
  domainSelectedPropUris,
  rangeSelectedPropUris,
}: GraphNodeTableProps) {
  const { columns, rows } = useMemo<{ columns: ColDef[]; rows: RowData[] }>(() => {
    if (mode === 'single') {
      const cls = classLabel ?? 'Node';
      const extraPropUris = domainSelectedPropUris ?? [];

      const cols: ColDef[] = [
        { key: `${cls}.uri`, label: `${cls}.uri`, align: 'left' },
        { key: `${cls}.label`, label: `${cls}.label`, align: 'left' },
        ...extraPropUris.map((propUri) => {
          const colKey = `${cls}.${uriFragment(propUri)}`;
          return { key: colKey, label: colKey, align: 'left' as const };
        }),
      ];

      const tableRows: RowData[] = (instances ?? []).map((inst) => {
        const cells: Record<string, string> = {
          [`${cls}.uri`]: inst.uri,
          [`${cls}.label`]: inst.label,
        };
        for (const propUri of extraPropUris) {
          const colKey = `${cls}.${uriFragment(propUri)}`;
          cells[colKey] = inst.properties[propUri] ?? '';
        }
        return { id: inst.uri, cells };
      });

      return { columns: cols, rows: tableRows };
    }

    // Dual mode
    const domCls = domainClassLabel ?? 'Domain';
    const rngCls = rangeClassLabel ?? 'Range';
    const domExtraUris = domainSelectedPropUris ?? [];
    const rngExtraUris = rangeSelectedPropUris ?? [];

    const cols: ColDef[] = [
      { key: `${domCls}.uri`, label: `${domCls}.uri`, align: 'left' },
      { key: `${domCls}.label`, label: `${domCls}.label`, align: 'left' },
      ...domExtraUris.map((propUri) => {
        const colKey = `${domCls}.${uriFragment(propUri)}`;
        return { key: colKey, label: colKey, align: 'left' as const };
      }),
      { key: 'Relation', label: 'Relation', align: 'left' },
      { key: `${rngCls}.uri`, label: `${rngCls}.uri`, align: 'left' },
      { key: `${rngCls}.label`, label: `${rngCls}.label`, align: 'left' },
      ...rngExtraUris.map((propUri) => {
        const colKey = `${rngCls}.${uriFragment(propUri)}`;
        return { key: colKey, label: colKey, align: 'left' as const };
      }),
    ];

    const tableRows: RowData[] = (relationRows ?? []).map((rel, idx) => {
      const cells: Record<string, string> = {
        [`${domCls}.uri`]: rel.domain_uri,
        [`${domCls}.label`]: rel.domain_label,
        Relation: rel.relation_label,
        [`${rngCls}.uri`]: rel.range_uri,
        [`${rngCls}.label`]: rel.range_label,
      };
      for (const propUri of domExtraUris) {
        const colKey = `${domCls}.${uriFragment(propUri)}`;
        cells[colKey] = rel.domain_properties[propUri] ?? '';
      }
      for (const propUri of rngExtraUris) {
        const colKey = `${rngCls}.${uriFragment(propUri)}`;
        cells[colKey] = rel.range_properties[propUri] ?? '';
      }
      return {
        id: `${rel.domain_uri}|${rel.relation_label}|${rel.range_uri}|${idx}`,
        cells,
      };
    });

    return { columns: cols, rows: tableRows };
  }, [
    mode,
    classLabel,
    instances,
    domainClassLabel,
    rangeClassLabel,
    relationRows,
    domainSelectedPropUris,
    rangeSelectedPropUris,
  ]);

  return <DataTable columns={columns} rows={rows} />;
}
