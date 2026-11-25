'use client';

import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { pageWindow, type PageWindow } from '@/app/settings/lib/pagination';
import './table-pager.css';

/** How many rows a settings table shows at once; the first is the default. */
export const PAGE_SIZES = [20, 50, 100] as const;
export type PageSize = (typeof PAGE_SIZES)[number];

export type PagedRows<T> = {
  /** The rows of the page shown. */
  pageRows: T[];
  window: PageWindow;
  size: PageSize;
  setSize: (size: PageSize) => void;
  setPage: (page: number) => void;
};

/**
 * A page of `rows`, which the caller has already searched, filtered and sorted (all of them,
 * not only a page). `resetKey` names what made them (the search, the filters, the sort): when
 * it changes, the table goes back to its first page. A smaller page size keeps the first row
 * shown in view.
 */
export function usePagedRows<T>(rows: readonly T[], resetKey: string): PagedRows<T> {
  const [state, setState] = useState<{ page: number; key: string }>({ page: 0, key: resetKey });
  const [size, setSizeState] = useState<PageSize>(PAGE_SIZES[0]);
  const page = state.key === resetKey ? state.page : 0;
  const window = pageWindow(rows.length, page, size);
  const pageRows = useMemo(() => rows.slice(window.start, window.end), [rows, window.start, window.end]);
  return {
    pageRows,
    window,
    size,
    setSize: (next) => {
      setSizeState(next);
      setState({ page: Math.floor(window.start / next), key: resetKey });
    },
    setPage: (next) => setState({ page: next, key: resetKey }),
  };
}

/**
 * Under a settings table: which rows show ("Rows 21–40 of 141"), how many a page holds (20, 50
 * or 100) and Previous / Next. Shown once the rows are more than the smallest page.
 */
export function TablePager<T>({ total, paged }: { total: number; paged: PagedRows<T> }) {
  if (total <= PAGE_SIZES[0]) return null;
  const { window, size, setSize, setPage } = paged;
  return (
    <nav className="settings-table-pager" aria-label="Table pages" data-pager="">
      <span data-field="rows-shown">
        Rows {(window.start + 1).toLocaleString()}–{window.end.toLocaleString()} of {total.toLocaleString()}
      </span>
      <span className="settings-table-pager-controls">
        <label className="settings-table-pager-size">
          Rows per page
          <select
            value={size}
            onChange={(event) => setSize(Number(event.target.value) as PageSize)}
            aria-label="Rows per page"
            data-field="page-size"
          >
            {PAGE_SIZES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="settings-table-pager-button"
          onClick={() => setPage(window.page - 1)}
          disabled={window.page === 0}
          aria-label="Previous page"
          data-action="previous-page"
        >
          <ChevronLeft size={14} />
          Previous
        </button>
        <span>
          Page {window.page + 1} of {window.pageCount}
        </span>
        <button
          type="button"
          className="settings-table-pager-button"
          onClick={() => setPage(window.page + 1)}
          disabled={window.page >= window.pageCount - 1}
          aria-label="Next page"
          data-action="next-page"
        >
          Next
          <ChevronRight size={14} />
        </button>
      </span>
    </nav>
  );
}
