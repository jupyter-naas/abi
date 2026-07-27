'use client';

import {
  useEffect,
  useMemo,
  useState,
} from 'react';

import {
  ColumnFilterPopover,
  formatColumnFilterChipLabel,
} from '@/components/dashboard/ColumnFilterPopover';
import { hasSerializedColumnFilter } from '@/lib/table/columnFilterUtils';
import { TableExportMenu } from '@/components/dashboard/TableExportMenu';
import { ThemeNumber } from '@/components/theme/ThemeNumber';
import { Button } from '@/components/ui/Button';
import {
  filterRecords,
  moveColumnKey,
  paginateRecords,
  reorderByKeys,
  searchRecords,
  sortRecords,
  toggleSort,
  type SortState,
} from '@/lib/table/dataTableUtils';
import type { NumberDisplayStyle, PercentInput } from '@/lib/theme/typography';

export type DataTableColumn = {
  key: string;
  label: string;
  align?: 'left' | 'right';
  valueStyle?: NumberDisplayStyle;
  percentInput?: PercentInput;
  currency?: string;
  maximumFractionDigits?: number;
  /** Extra classes for the body cell (`td`). */
  cellClassName?: string;
  renderCell?: (record: Record<string, unknown>) => React.ReactNode;
  /** Custom value rendering that keeps sorting/filtering enabled (unlike `renderCell`). */
  renderValue?: (value: unknown, record: Record<string, unknown>) => React.ReactNode;
  /** Custom header content (replaces the label; disables sort/filter UI for the column). */
  renderHeader?: () => React.ReactNode;
};

type DataTableProps = {
  records: Record<string, unknown>[];
  columns: DataTableColumn[];
  emptyMessage?: string;
  className?: string;
  maxHeight?: string;
  paginate?: boolean;
  defaultPageSize?: number;
  pageSizeOptions?: readonly number[];
  interactive?: boolean;
  columnFilters?: Record<string, string>;
  onColumnFiltersChange?: (filters: Record<string, string>) => void;
  showAllRows?: boolean;
  onShowAllRowsChange?: (showAllRows: boolean) => void;
  exportable?: boolean;
  exportFileName?: string;
  /** Extra controls rendered in the toolbar on the left (export stays on the right). */
  toolbarActions?: React.ReactNode;
  /** Sticky aggregate row (Excel-like SUBTOTAL) over the filtered rows. */
  summaryRow?: boolean;
  /** Shows a free-text search that matches any visible column. */
  globalSearch?: boolean;
  globalSearchPlaceholder?: string;
};

const DEFAULT_PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

const thClass =
  'sticky top-0 z-10 border border-[color-mix(in_srgb,#ffffff_22%,var(--secondary))] bg-[var(--secondary)] p-0 text-center text-xs font-semibold uppercase tracking-wide text-white whitespace-nowrap';

const tdClass =
  'border border-[color-mix(in_srgb,var(--text)_10%,var(--border))] px-3 py-1.5 align-middle whitespace-nowrap';

const tfootTdClass =
  'sticky bottom-0 z-10 border border-[color-mix(in_srgb,var(--text)_10%,var(--border))] border-t-2 border-t-[var(--secondary)] bg-[color-mix(in_srgb,var(--secondary)_10%,var(--surface))] px-3 py-2 align-middle font-semibold text-[var(--text)]';

type AggFn = 'sum' | 'count' | 'avg' | 'min' | 'max';

const AGG_FNS: readonly AggFn[] = ['sum', 'count', 'avg', 'min', 'max'];

const AGG_LABELS: Record<AggFn, string> = {
  sum: 'Somme',
  count: 'Nombre',
  avg: 'Moyenne',
  min: 'Min',
  max: 'Max',
};

function isNumericColumn(column: DataTableColumn): boolean {
  return (
    column.valueStyle === 'currency' ||
    column.valueStyle === 'decimal' ||
    column.valueStyle === 'percent' ||
    column.align === 'right'
  );
}

function columnNumbers(records: Record<string, unknown>[], key: string): number[] {
  const out: number[] = [];
  for (const record of records) {
    const value = record[key];
    if (typeof value === 'number' && Number.isFinite(value)) out.push(value);
  }
  return out;
}

function aggregate(nums: number[], fn: AggFn): number | null {
  if (fn === 'count') return nums.length;
  if (nums.length === 0) return null;
  switch (fn) {
    case 'sum':
      return nums.reduce((total, value) => total + value, 0);
    case 'avg':
      return nums.reduce((total, value) => total + value, 0) / nums.length;
    case 'min':
      return Math.min(...nums);
    case 'max':
      return Math.max(...nums);
  }
}

export function DataTable({
  records,
  columns,
  emptyMessage = 'Aucune donnée.',
  className = '',
  maxHeight = 'min(70vh, 800px)',
  paginate = true,
  defaultPageSize = 10,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
  interactive = true,
  columnFilters: columnFiltersProp,
  onColumnFiltersChange,
  showAllRows = false,
  onShowAllRowsChange,
  exportable = true,
  exportFileName = 'export',
  toolbarActions,
  summaryRow = false,
  globalSearch = false,
  globalSearchPlaceholder = 'Rechercher…',
}: DataTableProps) {
  const columnKeys = useMemo(() => columns.map((column) => column.key).join('|'), [columns]);

  const [columnOrder, setColumnOrder] = useState<string[]>(() => columns.map((c) => c.key));
  const [sort, setSort] = useState<SortState>(null);
  const [internalFilters, setInternalFilters] = useState<Record<string, string>>({});
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(defaultPageSize);
  const [aggFn, setAggFn] = useState<AggFn>('sum');
  const [dragCol, setDragCol] = useState<string | null>(null);
  const [dragOverCol, setDragOverCol] = useState<string | null>(null);
  const [dragInsertAfter, setDragInsertAfter] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const filters = columnFiltersProp ?? internalFilters;
  const setFilters = onColumnFiltersChange ?? setInternalFilters;

  useEffect(() => {
    setColumnOrder(columns.map((column) => column.key));
  }, [columnKeys, columns]);

  useEffect(() => {
    setPageIndex(0);
  }, [filters, sort, pageSize, showAllRows, records.length, searchQuery]);

  const orderedColumns = useMemo(
    () => reorderByKeys(columns, columnOrder),
    [columns, columnOrder],
  );

  const searchableKeys = useMemo(
    () => columns.map((column) => column.key),
    [columns],
  );

  const processedRecords = useMemo(() => {
    const searched = globalSearch
      ? searchRecords(records, searchQuery, searchableKeys)
      : records;
    const filtered = filterRecords(searched, filters);
    return sortRecords(filtered, sort);
  }, [records, filters, sort, globalSearch, searchQuery, searchableKeys]);

  const effectivePageSize = showAllRows
    ? Math.max(processedRecords.length, 1)
    : pageSize;

  const { pageRecords, totalPages, totalCount, safePageIndex } = useMemo(
    () =>
      paginate
        ? paginateRecords(processedRecords, pageIndex, effectivePageSize)
        : {
            pageRecords: processedRecords,
            totalPages: 1,
            totalCount: processedRecords.length,
            safePageIndex: 0,
          },
    [processedRecords, pageIndex, effectivePageSize, paginate],
  );

  useEffect(() => {
    if (safePageIndex !== pageIndex) {
      setPageIndex(safePageIndex);
    }
  }, [safePageIndex, pageIndex]);

  const rangeStart = totalCount === 0 ? 0 : safePageIndex * effectivePageSize + 1;
  const rangeEnd = paginate
    ? Math.min(totalCount, (safePageIndex + 1) * effectivePageSize)
    : totalCount;

  function handlePageSizeChange(nextPageSize: number) {
    onShowAllRowsChange?.(false);
    setPageSize(nextPageSize);
  }

  function updateColumnFilter(columnKey: string, value: string) {
    setFilters({ ...filters, [columnKey]: value });
  }

  function clearColumnFilter(columnKey: string) {
    const next = { ...filters };
    delete next[columnKey];
    setFilters(next);
  }

  const activeFilterEntries = useMemo(
    () =>
      Object.entries(filters).filter(([, value]) => hasSerializedColumnFilter(value)),
    [filters],
  );
  const hasActiveFilters = activeFilterEntries.length > 0;
  const showFilterBar = interactive && (hasActiveFilters || showAllRows);
  const showToolbar =
    (interactive && (exportable || showFilterBar || globalSearch)) ||
    Boolean(toolbarActions);

  function clearAllFilters() {
    setFilters({});
    onShowAllRowsChange?.(false);
  }

  function onColumnDrop(targetKey: string, insertAfter: boolean) {
    setDragOverCol(null);
    const dragged = dragCol;
    setDragCol(null);
    if (!dragged || dragged === targetKey) {
      return;
    }
    setColumnOrder((current) => moveColumnKey(current, dragged, targetKey, insertAfter));
  }

  if (records.length === 0) {
    return <p className="text-sm text-[var(--text-muted)]">{emptyMessage}</p>;
  }

  return (
    <div className={`flex flex-col gap-3 ${className}`.trim()}>
      {showToolbar ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            {globalSearch ? (
              <input
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder={globalSearchPlaceholder}
                aria-label={globalSearchPlaceholder}
                className="min-h-9 w-full max-w-sm rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text)] outline-none transition placeholder:text-[var(--text-muted)] focus:border-[var(--secondary)]"
              />
            ) : null}
            {toolbarActions}
            {showFilterBar ? (
              <>
                <span className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                  Filtres
                </span>
                {activeFilterEntries.map(([columnKey, value]) => {
                  const column = columns.find((entry) => entry.key === columnKey);
                  return (
                    <span
                      key={columnKey}
                      className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--accent)] px-3 py-1 text-xs text-[var(--text)]"
                    >
                      <span className="truncate">
                        <span className="font-semibold">{column?.label ?? columnKey}</span>
                        {' · '}
                        {formatColumnFilterChipLabel(value)}
                      </span>
                      <button
                        type="button"
                        onClick={() => clearColumnFilter(columnKey)}
                        className="shrink-0 rounded-full p-0.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)]"
                        aria-label={`Retirer le filtre ${column?.label ?? columnKey}`}
                      >
                        ×
                      </button>
                    </span>
                  );
                })}
                {showAllRows ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--accent)] px-3 py-1 text-xs text-[var(--text)]">
                    Toutes les lignes
                    <button
                      type="button"
                      onClick={() => onShowAllRowsChange?.(false)}
                      className="shrink-0 rounded-full p-0.5 text-[var(--text-muted)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)]"
                      aria-label="Revenir à la pagination par défaut"
                    >
                      ×
                    </button>
                  </span>
                ) : null}
                {hasActiveFilters && activeFilterEntries.length + (showAllRows ? 1 : 0) > 1 ? (
                  <button
                    type="button"
                    onClick={clearAllFilters}
                    className="text-xs text-[var(--secondary)] underline-offset-2 hover:underline outline-none focus-visible:ring-2 focus-visible:ring-[var(--secondary)]"
                  >
                    Tout effacer
                  </button>
                ) : null}
              </>
            ) : null}
          </div>
          {exportable ? (
            <div className="flex items-center gap-2">
              <TableExportMenu
                allRecords={records}
                filteredRecords={processedRecords}
                columns={orderedColumns}
                fileName={exportFileName}
              />
            </div>
          ) : null}
        </div>
      ) : null}
      <div
        className="min-w-0 overflow-auto border border-[var(--border)] bg-[var(--surface)] scrollbar-thin"
        style={{ maxHeight }}
      >
        <table className="w-max min-w-full border-collapse text-sm leading-snug">
          <thead>
            <tr>
              {orderedColumns.map((col) => {
                const sorted = sort?.columnKey === col.key;
                const sortDir = sorted ? sort.direction : null;
                const filterActive = hasSerializedColumnFilter(filters[col.key] ?? '');
                const isActionsColumn = Boolean(col.renderCell);
                const isDragging = dragCol === col.key;
                const isDropTarget = dragOverCol === col.key && dragCol !== col.key;

                return (
                  <th
                    key={col.key}
                    className={`${thClass} ${
                      isDragging ? 'opacity-40' : ''
                    } ${
                      isDropTarget && !dragInsertAfter
                        ? 'border-l-[3px] border-l-white'
                        : ''
                    } ${
                      isDropTarget && dragInsertAfter
                        ? 'border-r-[3px] border-r-white'
                        : ''
                    }`}
                    scope="col"
                    draggable={interactive}
                    onDragStart={(event) => {
                      if (!interactive) return;
                      setDragCol(col.key);
                      event.dataTransfer.effectAllowed = 'move';
                    }}
                    onDragOver={(event) => {
                      if (!interactive || col.key === dragCol) return;
                      event.preventDefault();
                      event.dataTransfer.dropEffect = 'move';
                      const rect = event.currentTarget.getBoundingClientRect();
                      setDragOverCol(col.key);
                      setDragInsertAfter(event.clientX > rect.left + rect.width / 2);
                    }}
                    onDragLeave={(event) => {
                      if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                        setDragOverCol(null);
                      }
                    }}
                    onDrop={(event) => {
                      if (!interactive) return;
                      event.preventDefault();
                      const rect = event.currentTarget.getBoundingClientRect();
                      onColumnDrop(
                        col.key,
                        event.clientX > rect.left + rect.width / 2,
                      );
                    }}
                    onDragEnd={() => {
                      setDragCol(null);
                      setDragOverCol(null);
                    }}
                  >
                    <div className="flex items-stretch">
                      {col.renderHeader ? (
                        <div className="flex min-w-0 flex-1 items-center justify-center gap-1 px-2 py-2">
                          {col.renderHeader()}
                        </div>
                      ) : (
                      <button
                        type="button"
                        onClick={() => {
                          if (!interactive || isActionsColumn) return;
                          setSort((current) => toggleSort(current, col.key));
                        }}
                        className={`flex min-w-0 flex-1 items-center justify-center gap-1 px-2 py-2 text-center transition-colors hover:bg-white/10 ${
                          sorted ? 'text-white' : 'text-white/90'
                        } ${isActionsColumn ? 'cursor-default hover:bg-transparent' : ''}`}
                        title={
                          interactive && !isActionsColumn
                            ? 'Trier (glisser l’en-tête pour réordonner)'
                            : undefined
                        }
                      >
                        {interactive && !isActionsColumn ? (
                          <span
                            className="shrink-0 cursor-grab text-[10px] text-white/50"
                            aria-hidden
                          >
                            ⋮⋮
                          </span>
                        ) : null}
                        <span className="truncate">{col.label}</span>
                        {interactive && sortDir === 'asc' ? (
                          <span className="shrink-0 text-[10px]" aria-hidden>
                            ▲
                          </span>
                        ) : null}
                        {interactive && sortDir === 'desc' ? (
                          <span className="shrink-0 text-[10px]" aria-hidden>
                            ▼
                          </span>
                        ) : null}
                      </button>
                      )}
                      {interactive && !isActionsColumn && !col.renderHeader ? (
                        <ColumnFilterPopover
                          columnKey={col.key}
                          label={col.label}
                          records={records}
                          value={filters[col.key] ?? ''}
                          active={filterActive}
                          onChange={(next) => updateColumnFilter(col.key, next)}
                          onClear={() => clearColumnFilter(col.key)}
                        />
                      ) : null}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRecords.length === 0 ? (
              <tr>
                <td
                  colSpan={orderedColumns.length}
                  className={`${tdClass} py-6 text-center text-sm text-[var(--text-muted)]`}
                >
                  Aucun résultat pour les filtres appliqués.
                </td>
              </tr>
            ) : (
              pageRecords.map((record, rowIndex) => (
                <tr key={rowIndex} className="hover:bg-[var(--accent)]">
                  {orderedColumns.map((col) => (
                    <td
                      key={col.key}
                      className={`${tdClass} ${col.align === 'right' ? 'text-right' : 'text-left'} ${col.cellClassName ?? ''}`.trim()}
                      title={cellTitle(record[col.key])}
                    >
                      <CellValue column={col} value={record[col.key]} record={record} />
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
          {summaryRow && orderedColumns.some(isNumericColumn) ? (
            <tfoot>
              <tr>
                {orderedColumns.map((col, index) => {
                  const numeric = isNumericColumn(col);
                  return (
                    <td
                      key={col.key}
                      className={`${tfootTdClass} ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                    >
                      {index === 0 ? (
                        <div className="flex items-center justify-between gap-2">
                          <AggregateSelector
                            fn={aggFn}
                            onChange={setAggFn}
                            count={processedRecords.length}
                          />
                          {numeric ? (
                            <AggregateValue
                              column={col}
                              fn={aggFn}
                              nums={columnNumbers(processedRecords, col.key)}
                            />
                          ) : null}
                        </div>
                      ) : numeric ? (
                        <AggregateValue
                          column={col}
                          fn={aggFn}
                          nums={columnNumbers(processedRecords, col.key)}
                        />
                      ) : null}
                    </td>
                  );
                })}
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>

      {paginate ? (
        <DataTableFooter
          totalCount={totalCount}
          rangeStart={rangeStart}
          rangeEnd={rangeEnd}
          pageIndex={safePageIndex}
          totalPages={totalPages}
          pageSize={showAllRows ? effectivePageSize : pageSize}
          showAllRows={showAllRows}
          pageSizeOptions={pageSizeOptions}
          onPageSizeChange={handlePageSizeChange}
          onShowAllRowsChange={onShowAllRowsChange}
          onPrevious={() => setPageIndex((current) => Math.max(0, current - 1))}
          onNext={() =>
            setPageIndex((current) => Math.min(totalPages - 1, current + 1))
          }
        />
      ) : null}
    </div>
  );
}

type DataTableFooterProps = {
  totalCount: number;
  rangeStart: number;
  rangeEnd: number;
  pageIndex: number;
  totalPages: number;
  pageSize: number;
  showAllRows: boolean;
  pageSizeOptions: readonly number[];
  onPageSizeChange: (size: number) => void;
  onShowAllRowsChange?: (showAllRows: boolean) => void;
  onPrevious: () => void;
  onNext: () => void;
};

function DataTableFooter({
  totalCount,
  rangeStart,
  rangeEnd,
  pageIndex,
  totalPages,
  pageSize,
  showAllRows,
  pageSizeOptions,
  onPageSizeChange,
  onShowAllRowsChange,
  onPrevious,
  onNext,
}: DataTableFooterProps) {
  return (
    <div className="flex flex-col gap-3 text-sm text-[var(--text-muted)] sm:flex-row sm:items-center sm:justify-between">
      <p>
        {totalCount === 0
          ? '0 ligne'
          : `${rangeStart}–${rangeEnd} sur ${totalCount} ligne${totalCount > 1 ? 's' : ''}`}
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wide">Afficher</span>
          <select
            value={showAllRows ? 'all' : String(pageSize)}
            onChange={(event) => {
              const value = event.target.value;
              if (value === 'all') {
                onShowAllRowsChange?.(true);
                return;
              }
              onPageSizeChange(Number(value));
            }}
            className="min-h-9 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm text-[var(--text)] outline-none focus:border-[var(--secondary)]"
            aria-label="Nombre de lignes par page"
          >
            <option value="all">
              Toutes{totalCount > 0 ? ` (${totalCount})` : ''}
            </option>
            {pageSizeOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            onPress={onPrevious}
            isDisabled={pageIndex <= 0}
            className="!w-auto !min-h-9 px-3 py-2 text-xs"
          >
            Précédent
          </Button>
          <span className="min-w-[6rem] text-center text-xs">
            Page {pageIndex + 1} / {totalPages}
          </span>
          <Button
            variant="ghost"
            onPress={onNext}
            isDisabled={pageIndex >= totalPages - 1}
            className="!w-auto !min-h-9 px-3 py-2 text-xs"
          >
            Suivant
          </Button>
        </div>
      </div>
    </div>
  );
}

function AggregateSelector({
  fn,
  onChange,
  count,
}: {
  fn: AggFn;
  onChange: (fn: AggFn) => void;
  count: number;
}) {
  return (
    <label className="flex min-w-0 items-center gap-2">
      <select
        value={fn}
        onChange={(event) => onChange(event.target.value as AggFn)}
        className="min-h-8 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs font-semibold text-[var(--text)] outline-none focus:border-[var(--secondary)]"
        aria-label="Fonction d’agrégation"
        title="Fonction d’agrégation (calculée sur les lignes filtrées)"
      >
        {AGG_FNS.map((option) => (
          <option key={option} value={option}>
            {AGG_LABELS[option]}
          </option>
        ))}
      </select>
      <span className="whitespace-nowrap text-xs font-normal text-[var(--text-muted)]">
        {count} ligne{count > 1 ? 's' : ''}
      </span>
    </label>
  );
}

function AggregateValue({
  column,
  fn,
  nums,
}: {
  column: DataTableColumn;
  fn: AggFn;
  nums: number[];
}) {
  const value = aggregate(nums, fn);
  if (value === null) {
    return <span className="text-[var(--text-muted)] opacity-60">—</span>;
  }
  if (fn === 'count') {
    return (
      <ThemeNumber
        value={value}
        style="decimal"
        maximumFractionDigits={0}
        className="inline-block tabular-nums"
      />
    );
  }
  return (
    <ThemeNumber
      value={value}
      style={column.valueStyle ?? 'decimal'}
      percentInput={column.percentInput}
      currency={column.currency}
      {...(column.maximumFractionDigits !== undefined
        ? { maximumFractionDigits: column.maximumFractionDigits }
        : {})}
      className="inline-block tabular-nums"
    />
  );
}

function CellValue({ column, value, record }: { column: DataTableColumn; value: unknown; record: Record<string, unknown> }) {
  if (column.renderCell) {
    return <>{column.renderCell(record)}</>;
  }

  if (value === null || value === undefined || value === '') {
    return <span className="text-[var(--text-muted)] opacity-60">—</span>;
  }

  if (column.renderValue) {
    return <>{column.renderValue(value, record)}</>;
  }

  if (typeof value === 'number' && column.valueStyle) {
    return (
      <ThemeNumber
        value={value}
        style={column.valueStyle}
        percentInput={column.percentInput}
        currency={column.currency}
        {...(column.maximumFractionDigits !== undefined
          ? { maximumFractionDigits: column.maximumFractionDigits }
          : {})}
        className="inline-block tabular-nums"
      />
    );
  }

  if (typeof value === 'number' && column.align === 'right') {
    return (
      <ThemeNumber
        value={value}
        style="decimal"
        {...(column.maximumFractionDigits !== undefined
          ? { maximumFractionDigits: column.maximumFractionDigits }
          : {})}
        className="inline-block tabular-nums"
      />
    );
  }

  return <span className="block">{String(value)}</span>;
}

function cellTitle(value: unknown): string | undefined {
  if (value === null || value === undefined || value === '') {
    return undefined;
  }
  return String(value);
}
