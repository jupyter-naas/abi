/** A raw database value as `GET /api/admin/tables/{name}` returns it. */
export type CellValue = string | number | boolean | null | Record<string, unknown> | unknown[];

export const NULL_LABEL = 'NULL';

/** Display, filter and export text for one cell. */
export function cellText(value: CellValue | undefined): string {
  if (value === null || value === undefined) return NULL_LABEL;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

/** Sorts NULLs last, numbers and booleans by value, everything else as text. */
export function compareCells(a: CellValue | undefined, b: CellValue | undefined): number {
  const aNull = a === null || a === undefined;
  const bNull = b === null || b === undefined;
  if (aNull || bNull) return aNull === bNull ? 0 : aNull ? 1 : -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'boolean' && typeof b === 'boolean') return Number(b) - Number(a);
  return cellText(a).localeCompare(cellText(b), undefined, { numeric: true });
}

/** Mask the API puts on secret columns (users.hashed_password); keep in sync with REDACTED. */
export const REDACTED_LABEL = '••••••';
