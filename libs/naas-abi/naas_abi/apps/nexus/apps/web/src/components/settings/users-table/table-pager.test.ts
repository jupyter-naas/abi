// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { createElement, useState } from 'react';
import { mount, type Mounted } from '@/lib/testing/mount';
import { TablePager, usePagedRows } from './table-pager';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const ROWS = Array.from({ length: 141 }, (_, i) => `row-${i + 1}`);

/** A table of `rows`, searched by the box above it (all the rows, not a page). */
function Table({ rows }: { rows: string[] }) {
  const [search, setSearch] = useState('');
  const shown = rows.filter((r) => r.includes(search));
  const paged = usePagedRows(shown, search);
  return createElement(
    'div',
    null,
    createElement('input', { 'data-field': 'search', value: search, onChange: (e: { target: { value: string } }) => setSearch(e.target.value) }),
    createElement('ul', null, ...paged.pageRows.map((r) => createElement('li', { key: r, 'data-row': r }, r))),
    createElement(TablePager, { total: shown.length, paged })
  );
}

const q = (selector: string) => mounted!.host.querySelector<HTMLElement>(selector);
const rows = () => [...mounted!.host.querySelectorAll('[data-row]')].map((li) => li.getAttribute('data-row'));

describe('a settings table, a page at a time', () => {
  it('shows 20 rows, then the next 20, then 50 or 100 a page', async () => {
    mounted = await mount(Table, { rows: ROWS });
    expect(rows()).toHaveLength(20);
    expect(q('[data-field="rows-shown"]')?.textContent).toBe('Rows 1–20 of 141');
    expect((q('[data-action="previous-page"]') as HTMLButtonElement).disabled).toBe(true);
    await mounted.click(q('[data-action="next-page"]'));
    expect(rows()[0]).toBe('row-21');
    await mounted.select(q('[data-field="page-size"]'), '100');
    // The first row shown stays in view: rows 1–100 hold row 21.
    expect(rows()).toHaveLength(100);
    expect(q('[data-field="rows-shown"]')?.textContent).toBe('Rows 1–100 of 141');
    await mounted.click(q('[data-action="next-page"]'));
    expect(rows()).toHaveLength(41);
    expect((q('[data-action="next-page"]') as HTMLButtonElement).disabled).toBe(true);
  });

  it('searches every row and goes back to the first page', async () => {
    mounted = await mount(Table, { rows: ROWS });
    await mounted.click(q('[data-action="next-page"]'));
    await mounted.type(q('[data-field="search"]'), 'row-14');
    // row-14 and row-140, row-141: found beyond the page that was shown.
    expect(rows()).toEqual(['row-14', 'row-140', 'row-141']);
    expect(q('[data-pager]')).toBeNull(); // no more than a page
  });
});
