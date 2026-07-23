/** Display label for empty cells in Excel-style column filters. */
export const EMPTY_FILTER_LABEL = '—';

/** Sentinel: column filter applied with zero values selected. */
export const NO_MATCH_COLUMN_FILTER = '__NO_MATCH__';

export function formatFilterValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return EMPTY_FILTER_LABEL;
  }
  return String(value);
}

export function collectUniqueColumnValues(
  records: Record<string, unknown>[],
  columnKey: string,
): string[] {
  const values = new Set<string>();
  for (const record of records) {
    values.add(formatFilterValue(record[columnKey]));
  }
  return Array.from(values).sort((a, b) =>
    a.localeCompare(b, 'fr', { numeric: true, sensitivity: 'base' }),
  );
}

export function parseColumnFilter(serialized: string): string[] | null {
  const trimmed = serialized.trim();
  if (!trimmed) {
    return null;
  }
  const values = trimmed
    .split('|')
    .map((value) => value.trim())
    .filter(Boolean);
  return values.length > 0 ? values : null;
}

export function serializeColumnFilter(values: Iterable<string>): string {
  return Array.from(values).join('|');
}

export function hasSerializedColumnFilter(serialized: string): boolean {
  return serialized.trim().length > 0;
}

export function formatFilterChipLabel(serialized: string): string {
  if (serialized === NO_MATCH_COLUMN_FILTER) {
    return 'aucune valeur';
  }
  const selected = parseColumnFilter(serialized);
  if (!selected) {
    return '';
  }
  if (selected.length <= 2) {
    return selected.join(', ');
  }
  return `${selected.length} valeurs`;
}

export function rowMatchesColumnFilter(
  row: Record<string, unknown>,
  columnKey: string,
  serializedFilter: string,
): boolean {
  if (serializedFilter === NO_MATCH_COLUMN_FILTER) {
    return false;
  }
  const selected = parseColumnFilter(serializedFilter);
  if (!selected) {
    return true;
  }
  const cell = formatFilterValue(row[columnKey]).toLowerCase();
  return selected.some((term) => cell === term.toLowerCase());
}
