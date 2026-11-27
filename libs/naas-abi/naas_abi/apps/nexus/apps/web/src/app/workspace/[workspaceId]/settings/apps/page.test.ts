// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const APPS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      app_id: `app-${n}`,
      app_name: `app-${n}`,
      module_path: 'acme.apps',
      name: `App ${n}`,
      description: i === 36 ? 'Counts the zebra herd' : `The app number ${n}`,
      // The last four are alpha: the "core" category keeps 41.
      category: i < 41 ? 'core' : 'alpha',
      url: `https://apps.example/${n}`,
      installed: true,
    };
  }),
);

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  usePathname: () => '/workspace/ws-1/settings/apps',
}));
vi.mock('@/stores/apps', () => ({
  useAppsStore: () => ({ apps: APPS, loading: false, fetchApps: async () => undefined }),
}));

import AppsSettingsPage from './page';
import { pickColumnFilter as pickFacet } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Apps', () => {
  it('shows 20 apps a page, searches and filters all of them from the columns, back to the first page', async () => {
    const m = (mounted = await mount(AppsSettingsPage, {}));
    await m.flush();
    const q = (selector: string) => m.host.querySelector(selector);
    const rows = () => [...m.host.querySelectorAll('[data-app]')].map((r) => r.getAttribute('data-app'));
    const shown = () => q('[data-field="rows-shown"]')?.textContent;

    expect([...m.host.querySelectorAll('[data-filter-trigger]')].map((b) => b.getAttribute('data-filter-trigger'))).toEqual(
      ['app', 'category', 'source'],
    );
    expect(q('select[aria-label="Category"]')).toBeNull();
    expect(rows()).toHaveLength(20);
    expect(shown()).toBe('Rows 1–20 of 45');
    expect(rows()).not.toContain('app-37');

    // The search reaches every row, not only the page shown.
    await m.type(q('input[placeholder="Search apps..."]'), 'zebra');
    expect(rows()).toEqual(['app-37']);
    expect(m.host.textContent).toContain('1 of 45 apps');
    await m.type(q('input[placeholder="Search apps..."]'), '');

    // The Category column filters, and goes back to the first page.
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toMatch(/^Rows 21–/);
    await pickFacet(m, 'category', 'core');
    expect(shown()).toBe('Rows 1–20 of 41');
    expect(m.host.textContent).toContain('41 of 45 apps');
    await m.click(q('[data-action="clear-filters"]'));
    expect(shown()).toBe('Rows 1–20 of 45');
  });

  it('sorts from a column header', async () => {
    const m = (mounted = await mount(AppsSettingsPage, {}));
    await m.flush();
    const first = () => m.host.querySelector('[data-app]')?.getAttribute('data-app');

    expect(first()).toBe('app-01');
    await m.click(m.host.querySelector('[data-sort="app"]'));
    expect(first()).toBe('app-45');
    await m.click(m.host.querySelector('[data-sort="category"]'));
    expect(first()).toBe('app-42');
  });
});
