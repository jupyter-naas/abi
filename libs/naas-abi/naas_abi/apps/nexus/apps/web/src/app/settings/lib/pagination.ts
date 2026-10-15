export const TABLE_PAGE_SIZE = 100;

export interface PageWindow {
  /** Zero-based page, clamped to the pages that exist. */
  page: number;
  pageCount: number;
  /** Slice bounds into the rows: rows.slice(start, end). */
  start: number;
  end: number;
}

/** The rows one page shows; an out-of-range page snaps to the last one. */
export function pageWindow(total: number, page: number, size = TABLE_PAGE_SIZE): PageWindow {
  const pageCount = Math.max(1, Math.ceil(total / size));
  const current = Math.min(Math.max(0, page), pageCount - 1);
  const start = current * size;
  return { page: current, pageCount, start, end: Math.min(total, start + size) };
}
