// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const ITEMS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      // The last four are pipelines: "Workflows" keeps 41.
      type: i < 41 ? 'workflow' : 'pipeline',
      module_id: 'acme.people',
      name: `flow-${n}`,
      display_name: `Flow ${n}`,
      description: i === 36 ? 'Moves the zebra herd' : '',
    };
  }),
);

// The URL's search: no policy picked ("<W> access") unless a test sets `?policy=`.
const URL_SEARCH = vi.hoisted(() => ({ current: '' }));

vi.mock('next/navigation', () => ({
  // `usePolicyHref` and the Enabled column read the policy picked from the URL.
  useSearchParams: () => new URLSearchParams(URL_SEARCH.current),
  useParams: () => ({ workspaceId: 'ws-1' }),
  usePathname: () => '/workspace/ws-1/settings/workflows',
}));
vi.mock('./workflows-model', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./workflows-model')>()),
  fetchWorkflowSettings: async () => ITEMS,
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

import WorkflowsSettingsPage from './workflows';
import { pickColumnFilter as pickFacet } from '@/lib/testing/column-filter';
import { moduleItemsFake } from '@/lib/testing/module-items-fake';

const enabledBox = (m: Mounted, key: string) =>
  m.host.querySelector(`input[data-enabled="${key}"]`) as HTMLInputElement | null;
const notice = (m: Mounted) => m.host.querySelector('[data-module-items-notice]')?.textContent ?? null;
const confirmButton = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find((b) => b.textContent === label)!;

/** acme.people's workflows offered whole, its pipeline not; acme.market's Prices not offered. */
const CATALOG = {
  modules: {
    'acme.people': { workflow: [{ name: 'flow-01' }, { name: 'flow-02' }], pipeline: [{ name: 'flow-42' }] },
    'acme.market': { workflow: [{ name: 'prices', label: 'Prices' }] },
  },
  offered: { workflows: [{ module: 'acme.people', name: '*' }] },
};

let mounted: Mounted | null = null;
beforeEach(() => {
  URL_SEARCH.current = '';
  moduleItemsFake.set({});
});
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Workflows', () => {
  it('shows 20 items a page, searches and filters all of them from the columns, back to the first page', async () => {
    const m = (mounted = await mount(WorkflowsSettingsPage, {}));
    await m.flush();
    const q = (selector: string) => m.host.querySelector(selector);
    const rows = () => [...m.host.querySelectorAll('[data-workflow]')].map((r) => r.getAttribute('data-workflow'));
    const shown = () => q('[data-field="rows-shown"]')?.textContent;

    expect(
      [...m.host.querySelectorAll('[data-filter-trigger]')].map((b) => b.getAttribute('data-filter-trigger')),
    ).toEqual(['name', 'type', 'module', 'enabled']);
    expect(q('select[aria-label="Type"]')).toBeNull();
    expect(rows()).toHaveLength(20);
    expect(shown()).toBe('Rows 1–20 of 45');
    await m.select(q('[data-field="page-size"]'), '50');
    expect(rows()).toHaveLength(45);
    await m.select(q('[data-field="page-size"]'), '20');

    // The search reaches every row, not only the page shown.
    await m.type(q('input[placeholder="Search workflows..."]'), 'zebra');
    expect(rows()).toEqual(['workflow/acme.people/flow-37']);
    // No count above the search: the badge says how many workflows, the pager how many are shown.
    expect(m.host.textContent).not.toContain('1 of 45');
    await m.type(q('input[placeholder="Search workflows..."]'), '');

    // The Type column filters, and goes back to the first page.
    await m.click(q('[data-action="next-page"]'));
    expect(shown()).toMatch(/^Rows 21–/);
    await pickFacet(m, 'type', 'workflow');
    expect(shown()).toBe('Rows 1–20 of 41');
    expect(rows().every((key) => key?.startsWith('workflow/'))).toBe(true);
    await m.click(q('[data-action="clear-filters"]'));
    expect(shown()).toBe('Rows 1–20 of 45');
  });

  it("says one total, and links each item's module to its row in Access › Modules", async () => {
    const m = (mounted = await mount(WorkflowsSettingsPage, {}));
    await m.flush();
    expect(m.host.textContent).toContain('45 workflows');
    expect(m.host.textContent).not.toContain('45 items');
    const link = m.host.querySelector('[data-workflow="workflow/acme.people/flow-01"] a[data-module-link]');
    expect(link?.getAttribute('href')).toBe('/workspace/ws-1/settings/modules?module=acme.people');
  });

  it('lists every workflow and pipeline of the modules, and disables one at once in the policy picked', async () => {
    URL_SEARCH.current = 'policy=pol_team';
    moduleItemsFake.set(CATALOG);
    const m = (mounted = await mount(WorkflowsSettingsPage, {}));
    await m.flush();
    // Prices is disabled: the list does not hold it, its row says what the catalog does.
    expect(m.host.textContent).toContain('46 workflows');
    expect(moduleItemsFake.reads).toEqual(['pol_team']);
    const flow = enabledBox(m, 'workflows|acme.people|flow-01');
    expect(flow?.closest('[data-workflow]')?.getAttribute('data-workflow')).toBe('workflow/acme.people/flow-01');
    expect(flow?.checked).toBe(true);
    // Disabling one of a module enabled whole turns its workflows item by item; its pipelines stay.
    await m.click(flow);
    await m.flush();
    expect(moduleItemsFake.saves).toEqual([
      {
        changes: [
          { kind: 'workflows', module: 'acme.people', name: '*', offered: false },
          { kind: 'workflows', module: 'acme.people', name: 'flow-02', offered: true },
        ],
        policyId: 'pol_team',
      },
    ]);
    expect(enabledBox(m, 'workflows|acme.people|flow-01')?.checked).toBe(false);
    expect(enabledBox(m, 'workflows|acme.people|flow-02')?.checked).toBe(true);
    expect(notice(m)).toBe('Flow 01 disabled.');
  });

  it('enables the rows a column filter keeps, selected all, in one save asked first', async () => {
    moduleItemsFake.set(CATALOG);
    const m = (mounted = await mount(WorkflowsSettingsPage, {}));
    await m.flush();
    await pickFacet(m, 'enabled', 'Disabled');
    expect([...m.host.querySelectorAll('[data-workflow]')].map((r) => r.getAttribute('data-workflow'))).toEqual([
      'workflow/acme.market/prices',
      'pipeline/acme.people/flow-42',
    ]);
    await m.click(m.host.querySelector('thead input[data-action="select-all"]'));
    expect(m.host.querySelector('[data-bulk-bar]')?.textContent).toContain('2 workflows selected');
    await m.click(m.host.querySelector('[data-bulk-bar] [data-bulk-action="on"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Enable 2 workflows?');
    await m.click(confirmButton('Enable'));
    await m.flush();
    expect(moduleItemsFake.saves).toHaveLength(1);
    expect(moduleItemsFake.saves[0].changes).toEqual(
      expect.arrayContaining([
        { kind: 'workflows', module: 'acme.market', name: 'prices', offered: true },
        { kind: 'pipelines', module: 'acme.people', name: 'flow-42', offered: true },
      ]),
    );
    expect(moduleItemsFake.saves[0].changes).toHaveLength(2);
    expect(notice(m)).toBe('2 workflows enabled.');
  });
});
