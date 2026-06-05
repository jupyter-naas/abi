'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  ListFilter,
  X,
  Search,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar } from './filter-bar';
import type { ChatTopRow } from '../lib/types';

type SortKey = keyof ChatTopRow;
type SortDir = 'asc' | 'desc';

const PAGE_SIZES = [20, 50, 100] as const;
type PageSize = typeof PAGE_SIZES[number];

type ColKey =
  | 'title'
  | 'user_email'
  | 'agent'
  | 'message_count'
  | 'likes'
  | 'dislikes'
  | 'last_message_at';

const COLUMNS: { key: ColKey; label: string; align: 'left' | 'right' }[] = [
  { key: 'title', label: 'Conversation', align: 'left' },
  { key: 'user_email', label: 'User', align: 'left' },
  { key: 'agent', label: 'Agent', align: 'left' },
  { key: 'message_count', label: 'Messages', align: 'right' },
  { key: 'likes', label: 'Likes', align: 'right' },
  { key: 'dislikes', label: 'Dislikes', align: 'right' },
  { key: 'last_message_at', label: 'Last message', align: 'right' },
];

interface Props {
  rows: ChatTopRow[];
  formatDateTime: (s: string) => string;
  onRowClick: (id: string) => void;
  onUserClick: (email: string) => void;
}

// Human-readable cell value used for filter matching and dropdown list
function displayValue(r: ChatTopRow, key: ColKey, formatDateTime: (s: string) => string): string {
  switch (key) {
    case 'title': return r.title || r.conversation_id;
    case 'user_email': return r.user_email ?? '(no user)';
    case 'agent': return r.agent ?? '(no agent)';
    case 'message_count': return String(r.message_count);
    case 'likes': return String(r.likes);
    case 'dislikes': return String(r.dislikes);
    case 'last_message_at': return r.last_message_at ? formatDateTime(r.last_message_at as string) : '(no date)';
  }
}

function sortValue(r: ChatTopRow, key: SortKey): string | number {
  switch (key) {
    case 'title': return r.title ?? r.conversation_id;
    case 'user_email': return r.user_email ?? '';
    case 'agent': return r.agent ?? '';
    case 'message_count': return r.message_count;
    case 'likes': return r.likes;
    case 'dislikes': return r.dislikes;
    case 'last_message_at': return r.last_message_at ?? '';
    default: return '';
  }
}

// ─── Excel-style checkbox filter dropdown ───────────────────────────────────

function FilterDropdown({
  availableValues,
  selectedValues,
  onChange,
  onClose,
  anchorRef,
}: {
  availableValues: string[];
  selectedValues: string[] | undefined; // undefined = all selected (no filter)
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
      // Align right edge of dropdown to right edge of anchor
      const left = Math.max(4, rect.right + window.scrollX - 208); // 208 = w-52
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

// ─── Main table ─────────────────────────────────────────────────────────────

export function ConversationsTable({ rows, formatDateTime, onRowClick, onUserClick }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('last_message_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  // filters: key present → active filter; undefined value never stored (key deleted instead)
  const [filters, setFilters] = useState<Partial<Record<ColKey, string[]>>>({});
  const [openFilter, setOpenFilter] = useState<ColKey | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(20);

  const filterBtnRefs = useRef<Partial<Record<ColKey, React.MutableRefObject<HTMLButtonElement | null>>>>({});
  COLUMNS.forEach(({ key }) => {
    if (!filterBtnRefs.current[key])
      filterBtnRefs.current[key] = { current: null } as React.MutableRefObject<HTMLButtonElement | null>;
  });

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('asc'); }
    setPage(1);
  }

  function applyFilter(col: ColKey, vals: string[] | undefined) {
    setFilters((prev) => {
      const next = { ...prev };
      if (vals === undefined) delete next[col];
      else next[col] = vals;
      return next;
    });
    setPage(1);
  }

  // Rows that pass ALL column filters
  const filtered = useMemo(() => {
    const entries = Object.entries(filters) as [ColKey, string[]][];
    if (entries.length === 0) return rows;
    return rows.filter((r) =>
      entries.every(([col, vals]) => vals.includes(displayValue(r, col, formatDateTime))),
    );
  }, [rows, filters, formatDateTime]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      const cmp = typeof av === 'number'
        ? av - (bv as number)
        : (av as string).localeCompare(bv as string);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  // For the open dropdown: unique values of that column from rows filtered by ALL OTHER columns
  const dropdownValues = useMemo((): string[] => {
    if (!openFilter) return [];
    const entries = Object.entries(filters) as [ColKey, string[]][];
    const rowsExcept = rows.filter((r) =>
      entries.every(([col, vals]) =>
        col === openFilter || vals.includes(displayValue(r, col, formatDateTime)),
      ),
    );
    const vals = rowsExcept.map((r) => displayValue(r, openFilter, formatDateTime));
    return [...new Set(vals)].sort((a, b) => a.localeCompare(b));
  }, [openFilter, rows, filters, formatDateTime]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageStart = (safePage - 1) * pageSize;
  const pageRows = sorted.slice(pageStart, pageStart + pageSize);

  const hasFilters = Object.keys(filters).length > 0;

  return (
    <div className="flex flex-col gap-3">
      {/* Active filter banner */}
      {hasFilters && (
        <div className="flex items-center gap-2 rounded border border-amber-200 bg-amber-50/70 dark:border-amber-800 dark:bg-amber-950/20 px-3 py-1.5 text-xs text-muted-foreground">
          <ListFilter className="h-3 w-3 shrink-0" />
          <span>{sorted.length} of {rows.length.toLocaleString()} row(s) shown</span>
          <button onClick={() => setFilters({})} className="ml-auto underline hover:text-foreground">
            Clear all filters
          </button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="bg-muted/60 text-muted-foreground">
              {COLUMNS.map(({ key, label, align }) => {
                const isActiveSort = sortKey === key;
                const isActiveFilter = key in filters;
                return (
                  <th
                    key={key}
                    className="border border-border px-0 py-0 text-left"
                  >
                    {/* Always: [sort label flex-1] [filter icon on the right] */}
                    <div className="flex items-stretch">
                      <button
                        onClick={() => toggleSort(key as SortKey)}
                        className={cn(
                          'flex flex-1 items-center gap-1 px-2 py-2 font-semibold uppercase tracking-wide select-none transition-colors hover:bg-muted/80',
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

                      {/* Filter icon — always pinned to the right */}
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
                          'flex shrink-0 items-center border-l border-border px-1.5 py-2 transition-colors hover:bg-muted/80',
                          isActiveFilter
                            ? 'text-workspace-accent bg-workspace-accent/5'
                            : 'text-muted-foreground hover:text-foreground',
                        )}
                        title={isActiveFilter
                          ? `Filter active (${(filters[key] ?? []).length} value(s))`
                          : 'Filter'}
                      >
                        <ListFilter className={cn('h-3 w-3', isActiveFilter && 'fill-workspace-accent/20')} />
                      </button>

                      {openFilter === key && (
                        <FilterDropdown
                          availableValues={dropdownValues}
                          selectedValues={filters[key]}
                          onChange={(vals) => applyFilter(key, vals)}
                          onClose={() => setOpenFilter(null)}
                          anchorRef={filterBtnRefs.current[key] as React.MutableRefObject<HTMLButtonElement | null>}
                        />
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((c, i) => (
              <tr
                key={c.conversation_id}
                className={cn(
                  'cursor-pointer transition-colors',
                  i % 2 === 0
                    ? 'bg-background hover:bg-muted/30'
                    : 'bg-muted/20 hover:bg-muted/40',
                )}
                onClick={() => onRowClick(c.conversation_id)}
              >
                <td className="border border-border px-2 py-1.5">
                  <div className="flex flex-col min-w-0">
                    <span className="font-medium truncate max-w-[220px] text-foreground">
                      {c.title || c.conversation_id}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground truncate max-w-[220px]">
                      {c.conversation_id}
                    </span>
                  </div>
                </td>
                <td className="border border-border px-2 py-1.5">
                  {c.user_email ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); onUserClick(c.user_email as string); }}
                      className="flex items-center gap-1.5 hover:underline"
                    >
                      <Avatar email={c.user_email} size={18} />
                      <span className="truncate max-w-[160px]">{c.user_email}</span>
                    </button>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="border border-border px-2 py-1.5 text-muted-foreground">
                  {c.agent ?? '—'}
                </td>
                <td className="border border-border px-2 py-1.5 text-right tabular-nums font-medium">
                  {c.message_count}
                </td>
                <td className="border border-border px-2 py-1.5 text-right tabular-nums text-emerald-600">
                  {c.likes > 0 ? c.likes : <span className="text-muted-foreground">—</span>}
                </td>
                <td className="border border-border px-2 py-1.5 text-right tabular-nums text-red-600">
                  {c.dislikes > 0 ? c.dislikes : <span className="text-muted-foreground">—</span>}
                </td>
                <td className="border border-border px-2 py-1.5 text-right text-muted-foreground">
                  {c.last_message_at ? formatDateTime(c.last_message_at) : '—'}
                </td>
              </tr>
            ))}

            {pageRows.length === 0 && (
              <tr>
                <td
                  colSpan={COLUMNS.length}
                  className="border border-border px-5 py-10 text-center text-sm text-muted-foreground"
                >
                  No conversations match the current filters.
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
            : `${pageStart + 1}–${Math.min(pageStart + pageSize, sorted.length)} of ${sorted.length.toLocaleString()} conversation(s)`}
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
