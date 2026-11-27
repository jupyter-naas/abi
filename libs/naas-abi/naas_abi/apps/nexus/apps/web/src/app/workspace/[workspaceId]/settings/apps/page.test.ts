// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const APPS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      app_id: `app-${n}`,
      app_name: `app-${n}`,
      module_path: 'acme.apps',
      module_name: 'acme.apps',
      name: `App ${n}`,
      description: i === 36 ? 'Counts the zebra herd' : `The app number ${n}`,
      // The last four are alpha: the "core" category keeps 41.
      category: i < 41 ? 'core' : 'alpha',
      url: `https://apps.example/${n}`,
      installed: true,
    };
  }),
);

// The URL's search: no policy picked ("<W> access") unless a test sets `?policy=`.
const URL_SEARCH = vi.hoisted(() => ({ current: '' }));

vi.mock('next/navigation', () => ({
  // `usePolicyHref` and the Enabled column read the policy picked from the URL.
  useSearchParams: () => new URLSearchParams(URL_SEARCH.current),
  useParams: () => ({ workspaceId: 'ws-1' }),
  usePathname: () => '/workspace/ws-1/settings/apps',
}));
vi.mock('@/stores/apps', () => ({
  useAppsStore: () => ({ apps: APPS, loading: false, fetchApps: async () => undefined }),
}));

// The module items: the offer and IAM's catalog, faked.
vi.mock('@/lib/access-model/workspace-offer', async (importOriginal) => {
  const { moduleItemsFake } = await import('@/lib/testing/module-items-fake');
  return { ...(await importOriginal<object>()), createOfferApi: () => moduleItemsFake.offer };
});
vi.mock('@/lib/iam-admin/api', async (importOriginal) => {
  const { moduleItemsFake } = await import('@/lib/testing/module-items-fake');
  return { ...(await importOriginal<object>()), createIamAdminApi: () => moduleItemsFake.iam };
});
vi.mock('@/hooks/use-workspace-resources', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  reloadWorkspaceResources: async () => undefined,
}));

import AppsSettingsPage from './page';
import { pickColumnFilter as pickFacet } from '@/lib/testing/column-filter';
import { moduleItemsFake } from '@/lib/testing/module-items-fake';

const enabledBox = (m: Mounted, key: string) =>
  m.host.querySelector(`input[data-enabled="${key}"]`) as HTMLInputElement | null;
const notice = (m: Mounted) => m.host.querySelector('[data-module-items-notice]')?.textContent ?? null;
const confirmButton = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find((b) => b.textContent === label)!;

let mounted: Mounted | null = null;
beforeEach(() => {
  URL_SEARCH.current = '';
  moduleItemsFake.set({});
});
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
      ['app', 'category', 'source', 'enabled'],
    );
    expect(q('select[aria-label="Category"]')).toBeNull();
    expect(rows()).toHaveLength(20);
    expect(shown()).toBe('Rows 1–20 of 45');
    expect(rows()).not.toContain('app-37');

    // The search reaches every row, not only the page shown.
    await m.type(q('input[placeholder="Search apps..."]'), 'zebra');
    expect(rows()).toEqual(['app-37']);
    // No count above the search: the badge says how many apps, the pager how many are shown.
    expect(m.host.textContent).not.toContain('1 of 45 apps');
    await m.type(q('input[placeholder="Search apps..."]'), '');

    // The Category column filters, and goes back to the first page.
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toMatch(/^Rows 21–/);
    await pickFacet(m, 'category', 'core');
    expect(shown()).toBe('Rows 1–20 of 41');
    await m.click(q('[data-action="clear-filters"]'));
    expect(shown()).toBe('Rows 1–20 of 45');
  });

  it("links each app's module to its row in Access › Modules, and sends to Access › Policies", async () => {
    const m = (mounted = await mount(AppsSettingsPage, {}));
    await m.flush();
    expect(m.host.textContent).toContain('45 apps');
    const link = m.host.querySelector('[data-app="app-01"] a[data-module-link]');
    expect(link?.getAttribute('href')).toBe('/workspace/ws-1/settings/modules?module=acme.apps');
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

  it('lists every app of the modules, enabled or not, and enables one at once in the policy picked', async () => {
    URL_SEARCH.current = 'policy=pol_team';
    moduleItemsFake.set({ modules: { 'acme.docs': { app: [{ name: 'notes', label: 'Notes' }] } } });
    const m = (mounted = await mount(AppsSettingsPage, {}));
    await m.flush();
    // Notes is disabled: the caller may not open it, its row says what the catalog does.
    expect(m.host.textContent).toContain('46 apps');
    await m.type(m.host.querySelector('input[placeholder="Search apps..."]'), 'Notes');
    const row = m.host.querySelector('[data-app="apps|acme.docs|notes"]');
    expect(row?.querySelector('a[data-module-link]')?.getAttribute('href')).toBe(
      '/workspace/ws-1/settings/modules?module=acme.docs&policy=pol_team',
    );
    expect(enabledBox(m, 'apps|acme.docs|notes')?.checked).toBe(false);
    await m.click(enabledBox(m, 'apps|acme.docs|notes'));
    await m.flush();
    expect(moduleItemsFake.saves).toEqual([
      { changes: [{ kind: 'apps', module: 'acme.docs', name: 'notes', offered: true }], policyId: 'pol_team' },
    ]);
    expect(enabledBox(m, 'apps|acme.docs|notes')?.checked).toBe(true);
    expect(notice(m)).toBe('Notes enabled.');
  });

  it('disables the apps shown, selected all, in one save: a module enabled whole goes item by item', async () => {
    moduleItemsFake.set({
      modules: {
        'acme.docs': {
          app: [
            { name: 'notes', label: 'Shared notes' },
            { name: 'pad', label: 'Shared pad' },
            { name: 'wiki', label: 'Wiki' },
          ],
        },
      },
      offered: { apps: [{ module: 'acme.docs', name: '*' }] },
    });
    const m = (mounted = await mount(AppsSettingsPage, {}));
    await m.flush();
    // The search keeps the two shared apps: select all takes those shown, not Wiki.
    await m.type(m.host.querySelector('input[placeholder="Search apps..."]'), 'shared');
    expect(m.host.querySelectorAll('[data-app]')).toHaveLength(2);
    await m.click(m.host.querySelector('thead input[data-action="select-all"]'));
    expect(m.host.querySelector('[data-bulk-bar]')?.textContent).toContain('2 apps selected');
    await m.click(m.host.querySelector('[data-bulk-bar] [data-bulk-action="off"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Disable 2 apps?');
    await m.click(confirmButton('Disable'));
    await m.flush();
    expect(moduleItemsFake.saves).toEqual([
      {
        changes: [
          { kind: 'apps', module: 'acme.docs', name: '*', offered: false },
          { kind: 'apps', module: 'acme.docs', name: 'wiki', offered: true },
        ],
        policyId: null,
      },
    ]);
    expect(enabledBox(m, 'apps|acme.docs|notes')?.checked).toBe(false);
    expect(notice(m)).toBe('2 apps disabled.');
    await m.type(m.host.querySelector('input[placeholder="Search apps..."]'), 'wiki');
    expect(enabledBox(m, 'apps|acme.docs|wiki')?.checked).toBe(true);
  });

  it('cannot change an app no module item answers to: enabled, its box locked, not selectable', async () => {
    const m = (mounted = await mount(AppsSettingsPage, {}));
    await m.flush();
    const row = m.host.querySelector('[data-app="app-01"]');
    const box = row?.querySelector('[data-field="enabled"] input') as HTMLInputElement | null;
    expect(box?.checked).toBe(true);
    expect(box?.disabled).toBe(true);
    expect((row?.querySelector('input[data-select-row]') as HTMLInputElement | null)?.disabled).toBe(true);
  });
});
