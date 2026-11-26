/** Checks of a settings table paged by `usePagedRows` and `TablePager` (component tests). */
import { expect } from 'vitest';
import { pickColumnFilter } from './column-filter';
import type { Mounted } from './mount';

export interface PagedTableCase {
  /** The attribute that marks a row of the table, its value the row's id: `data-agent`. */
  row: string;
  /** How many rows the table holds before any search or filter. */
  total: number;
  /** The search box above the table. */
  search: string;
  /** A row beyond the first page, and a search that lists it. */
  far: { id: string; query: string };
  /** A filter that keeps more than a page of rows: its select, or its column (a funnel of
   *  `SettingsTableHead`), and the value to pick. */
  filter: { select: string; value: string } | { column: string; value: string };
}

/**
 * As a person uses the table: 20 rows a page (50 on demand), Next; a search finds a row
 * beyond the first page; a change of a filter goes back to the first page.
 */
export async function checkPagedTable(mounted: Mounted, c: PagedTableCase): Promise<void> {
  const q = (selector: string) => mounted.host.querySelector(selector);
  const rows = () => [...mounted.host.querySelectorAll(`[${c.row}]`)].map((r) => r.getAttribute(c.row));
  const shown = () => q('[data-field="rows-shown"]')?.textContent ?? null;

  // The page size.
  expect(rows()).toHaveLength(20);
  expect(shown()).toBe(`Rows 1–20 of ${c.total}`);
  expect(rows()).not.toContain(c.far.id);
  await mounted.select(q('[data-field="page-size"]'), '50');
  expect(rows()).toHaveLength(Math.min(50, c.total));
  await mounted.select(q('[data-field="page-size"]'), '20');
  await mounted.click(q('[data-action="next-page"]'));
  expect(shown()).toBe(`Rows 21–${Math.min(40, c.total)} of ${c.total}`);

  // The search reaches every row, not only the page shown.
  await mounted.type(q(c.search), c.far.query);
  expect(rows()).toContain(c.far.id);
  expect(mounted.host.textContent).toContain(`of ${c.total}`);

  // A change of a filter goes back to the first page.
  await mounted.type(q(c.search), '');
  await mounted.click(q('[data-action="next-page"]'));
  expect(shown()).toMatch(/^Rows 21–/);
  if ('select' in c.filter) await mounted.select(q(c.filter.select), c.filter.value);
  else await pickColumnFilter(mounted, c.filter.column, c.filter.value);
  expect(shown()).toMatch(/^Rows 1–20 of /);
}
