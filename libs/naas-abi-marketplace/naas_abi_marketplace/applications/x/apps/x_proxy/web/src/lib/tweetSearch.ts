/**
 * Column-filter state for the tweet tables, and the published value lists
 * behind the checkbox pickers.
 *
 * Filtering is applied in the browser against the rows the snapshot already
 * carries. The *option lists*, though, come from `search_recents_tweets/
 * facets.json`, which is aggregated over the whole query + window at publish
 * time — so ticking a username offers every author in the window, not only the
 * ones visible in the loaded page.
 */
import type { FacetEntry, FacetValue } from "@/lib/types";

/** Columns whose distinct values are enumerable as checkboxes. */
export const FACET_COLUMNS = ["username", "location", "verified_type"];

export type ColumnFilterState = {
  /** Case-insensitive substring match. */
  contains: string;
  /** Exact values ticked in the checkbox list (OR within a column). */
  values: string[];
};

export type ColumnFilters = Record<string, ColumnFilterState>;

export type ColumnValue = FacetValue;

export function isFilterActive(state?: ColumnFilterState): boolean {
  if (!state) return false;
  return Boolean(state.contains.trim()) || state.values.length > 0;
}

export function activeFilterCount(filters: ColumnFilters): number {
  return Object.values(filters).filter(isFilterActive).length;
}

/** The published option list for one column of a query + scenario. */
export function facetValues(
  facets: FacetEntry[] | undefined,
  querySlug: string,
  scenarioId: string,
  column: string,
): ColumnValue[] {
  const entry = (facets || []).find(
    (f) =>
      f.query_slug === querySlug &&
      f.scenario_id === scenarioId &&
      f.column === column,
  );
  return entry?.values || [];
}

/** True when a row passes every active column filter. */
export function rowMatches(
  row: Record<string, unknown>,
  filters: ColumnFilters,
): boolean {
  return Object.entries(filters).every(([column, state]) => {
    if (!isFilterActive(state)) return true;
    const cell = String(row[column] ?? "");
    const contains = state.contains.trim().toLowerCase();
    if (contains && !cell.toLowerCase().includes(contains)) return false;
    if (state.values.length && !state.values.includes(cell)) return false;
    return true;
  });
}
