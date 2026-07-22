import { rowMatchesColumnFilter } from '@/lib/table/columnFilterUtils';

export type SortDirection = 'asc' | 'desc';

export type SortState = {
  columnKey: string;
  direction: SortDirection;
} | null;

export function compareCellValues(a: unknown, b: unknown): number {
  if (a === b) return 0;
  if (a === null || a === undefined || a === '') return 1;
  if (b === null || b === undefined || b === '') return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'number') return -1;
  if (typeof b === 'number') return 1;
  return String(a).localeCompare(String(b), 'fr', { numeric: true, sensitivity: 'base' });
}

export function filterRecords(
  records: Record<string, unknown>[],
  filters: Record<string, string>,
): Record<string, unknown>[] {
  const active = Object.entries(filters).filter(([, value]) => value.trim());
  if (active.length === 0) {
    return records;
  }

  return records.filter((row) =>
    active.every(([key, text]) => rowMatchesColumnFilter(row, key, text)),
  );
}

/** Case-insensitive substring match across all (or selected) column values. */
export function searchRecords(
  records: Record<string, unknown>[],
  query: string,
  columnKeys?: readonly string[],
): Record<string, unknown>[] {
  const needle = query.trim().toLocaleLowerCase('fr');
  if (!needle) {
    return records;
  }

  return records.filter((row) => {
    const keys = columnKeys ?? Object.keys(row);
    return keys.some((key) => {
      const value = row[key];
      if (value === null || value === undefined) {
        return false;
      }
      return String(value).toLocaleLowerCase('fr').includes(needle);
    });
  });
}

export function sortRecords(
  records: Record<string, unknown>[],
  sort: SortState,
): Record<string, unknown>[] {
  if (!sort) {
    return records;
  }

  const multiplier = sort.direction === 'asc' ? 1 : -1;
  return [...records].sort(
    (a, b) => multiplier * compareCellValues(a[sort.columnKey], b[sort.columnKey]),
  );
}

export function paginateRecords<T>(
  records: T[],
  pageIndex: number,
  pageSize: number,
): {
  pageRecords: T[];
  totalPages: number;
  totalCount: number;
  safePageIndex: number;
} {
  const totalCount = records.length;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const safePageIndex = Math.min(Math.max(0, pageIndex), totalPages - 1);
  const start = safePageIndex * pageSize;

  return {
    pageRecords: records.slice(start, start + pageSize),
    totalPages,
    totalCount,
    safePageIndex,
  };
}

export function reorderByKeys<T extends { key: string }>(
  columns: T[],
  order: string[],
): T[] {
  const byKey = new Map(columns.map((column) => [column.key, column]));
  const next: T[] = [];

  for (const key of order) {
    const column = byKey.get(key);
    if (column) {
      next.push(column);
      byKey.delete(key);
    }
  }

  for (const column of byKey.values()) {
    next.push(column);
  }

  return next;
}

export function moveColumnKey(
  order: string[],
  draggedKey: string,
  targetKey: string,
  insertAfter: boolean,
): string[] {
  if (draggedKey === targetKey) {
    return order;
  }

  const next = order.filter((key) => key !== draggedKey);
  let targetIndex = next.indexOf(targetKey);
  if (targetIndex === -1) {
    return order;
  }
  if (insertAfter) {
    targetIndex += 1;
  }
  next.splice(targetIndex, 0, draggedKey);
  return next;
}

export function toggleSort(current: SortState, columnKey: string): SortState {
  if (current?.columnKey !== columnKey) {
    return { columnKey, direction: 'asc' };
  }
  if (current.direction === 'asc') {
    return { columnKey, direction: 'desc' };
  }
  return null;
}
