import type { WorkbookSheet } from '@/app/organizations/[orgId]/settings/users/users-table-export';
import { cellText, type CellValue } from './table-cells';

/** One table, as `GET /api/admin/tables/{name}` returns it. */
export interface ExportedTable {
  name: string;
  description: string;
  columns: string[];
  rows: Record<string, CellValue>[];
  total: number;
  truncated: boolean;
}

/** JSON export: every table with its columns and rows, as the API serves them. */
export function buildJsonExport(tables: readonly ExportedTable[], exportedAt: Date) {
  return {
    exported_at: exportedAt.toISOString(),
    tables: Object.fromEntries(
      tables.map((table) => [
        table.name,
        {
          description: table.description,
          columns: table.columns,
          total: table.total,
          truncated: table.truncated,
          rows: table.rows,
        },
      ])
    ),
  };
}

/** Excel export: one sheet per table, named after it, every column as text. */
export function buildWorkbookSheets(tables: readonly ExportedTable[]): WorkbookSheet[] {
  return tables.map((table) => ({
    name: table.name,
    headers: table.columns,
    rows: table.rows.map((row) => table.columns.map((column) => cellText(row[column]))),
  }));
}

/** Runs `task` over `items`, at most `limit` at a time, keeping the input order. */
export async function mapWithLimit<T, R>(
  items: readonly T[],
  limit: number,
  task: (item: T) => Promise<R>
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;
  const worker = async () => {
    while (next < items.length) {
      const index = next++;
      results[index] = await task(items[index]);
    }
  };
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker));
  return results;
}
