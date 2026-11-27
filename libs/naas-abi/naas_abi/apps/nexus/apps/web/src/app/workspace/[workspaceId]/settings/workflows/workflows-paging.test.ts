// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
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

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  usePathname: () => '/workspace/ws-1/settings/workflows',
}));
vi.mock('./workflows-model', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./workflows-model')>()),
  fetchWorkflowSettings: async () => ITEMS,
}));

import WorkflowsSettingsPage from './workflows';
import { pickColumnFilter as pickFacet } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
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
    ).toEqual(['name', 'type', 'module']);
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
});
