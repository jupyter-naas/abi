// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const SNAPSHOT = vi.hoisted(() => ({
  data: { enabled: ['onto-02'] } as Record<string, unknown>,
  revision: 1,
  updated_by: null,
  catalog: Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      id: `onto-${n}`,
      name: `Ontology ${n}`,
      description: i === 36 ? 'Of the zebra herd' : `The ontology number ${n}`,
      // The last four are unavailable: "Available" keeps 41.
      available: i < 41,
    };
  }),
}));

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  usePathname: () => '/workspace/ws-1/settings/ontologies',
}));
// Each write: its body kept, answered with the policy it sends at the next revision.
const PUTS = vi.hoisted(() => [] as { revision: number; policy: Record<string, unknown> }[]);
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  authFetch: async (url: string, init?: RequestInit) => {
    if (init?.method === 'PUT') {
      const body = JSON.parse(String(init.body));
      PUTS.push(body);
      return new Response(JSON.stringify({ ...SNAPSHOT, data: body.policy, revision: body.revision + 1 }), { status: 200 });
    }
    return new Response(
      JSON.stringify(
        url.endsWith('/graphs')
          ? { ...SNAPSHOT, data: { read: ['onto-03'], write: ['onto-04'] } }
          : SNAPSHOT,
      ),
      { status: 200 },
    );
  },
}));
vi.mock('@/stores/graph-explorer', () => ({ invalidateGraphExplorer: () => undefined }));
vi.mock('@/stores/ontology', () => ({ useOntologyStore: { setState: () => undefined } }));

import { ResourceAccessEditor } from './resource-access';
import { pickColumnFilter as filterColumn } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  PUTS.length = 0;
});
const confirmButton = (label: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find((b) => b.textContent === label)!;
const notice = () => mounted!.host.querySelector('[data-resource-notice]')?.textContent ?? null;

const rows = () => [...mounted!.host.querySelectorAll('[data-resource]')].map((r) => r.getAttribute('data-resource'));
const shown = () => mounted!.host.querySelector('[data-field="rows-shown"]')?.textContent;

describe('Workspace settings › Ontologies (resource access)', () => {
  it('shows 20 rows a page and searches all of them', async () => {
    mounted = await mount(ResourceAccessEditor, { workspaceId: 'ws-1', kind: 'ontologies' });
    await mounted.flush();
    expect(rows()).toHaveLength(20);
    expect(shown()).toBe('Rows 1–20 of 45');
    expect(rows()).not.toContain('onto-37');
    await mounted.click(mounted.host.querySelector('[data-action="next-page"]'));
    expect(shown()).toBe('Rows 21–40 of 45');

    await mounted.type(mounted.host.querySelector('input[placeholder="Search ontologies…"]'), 'zebra');
    expect(rows()).toEqual(['onto-37']);
    // One total in the badge, no count above the search.
    expect(mounted.host.textContent).toContain('45 ontologies');
    expect(mounted.host.textContent).not.toContain('1 of 45 ontologies');
  });

  it('filters Availability and Enabled from their columns, back to the first page', async () => {
    mounted = await mount(ResourceAccessEditor, { workspaceId: 'ws-1', kind: 'ontologies' });
    await mounted.flush();
    expect(mounted.host.querySelector('select[aria-label="Availability"]')).toBeNull();
    await mounted.click(mounted.host.querySelector('[data-action="next-page"]'));

    await filterColumn(mounted, 'availability', 'Available');
    expect(shown()).toBe('Rows 1–20 of 41');
    await filterColumn(mounted, 'availability', 'Available');
    await filterColumn(mounted, 'availability', 'Unavailable');
    expect(rows()).toEqual(['onto-42', 'onto-43', 'onto-44', 'onto-45']);

    await mounted.click(mounted.host.querySelector('[data-action="clear-filters"]'));
    await filterColumn(mounted, 'enabled', 'Enabled');
    expect(rows()).toEqual(['onto-02']);
    // Each change is saved at once: a row unticked under the filter leaves the table.
    await mounted.click(mounted.host.querySelector('[aria-label="Enable Ontology 02"]'));
    await mounted.flush();
    expect(PUTS).toEqual([{ revision: 1, policy: { enabled: [] } }]);
    expect(notice()).toBe('Ontology 02 disabled.');
    expect(rows()).toEqual([]);
    expect(mounted.host.textContent).toContain('No ontologies match the current search and filters');
    // No Save button: a table of switches.
    expect([...mounted.host.querySelectorAll('button')].map((b) => b.textContent)).not.toContain('Save changes');
  });

  it("says it sets the workspace's own ontologies when another policy is picked in the column", async () => {
    mounted = await mount(ResourceAccessEditor, { workspaceId: 'ws-1', kind: 'ontologies', policyPicked: true });
    await mounted.flush();
    expect(mounted.host.querySelector('[data-policy-note]')?.textContent).toContain('whatever policy is picked');
  });

  it('enables the ontologies selected in one save, asked first', async () => {
    mounted = await mount(ResourceAccessEditor, { workspaceId: 'ws-1', kind: 'ontologies' });
    await mounted.flush();
    await mounted.type(mounted.host.querySelector('input[placeholder="Search ontologies…"]'), 'Ontology 0');
    await mounted.click(mounted.host.querySelector('thead input[data-action="select-all"]'));
    // The search reads each word: "0" keeps 01 to 09, 10, 20, 30 and 40.
    expect(mounted.host.querySelector('[data-bulk-bar]')?.textContent).toContain('13 ontologies selected');
    await mounted.click(mounted.host.querySelector('[data-bulk-action="on"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Enable 13 ontologies?');
    await mounted.click(confirmButton('Enable'));
    await mounted.flush();
    expect(PUTS).toHaveLength(1);
    expect([...(PUTS[0].policy.enabled as string[])].sort()).toEqual(
      ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '20', '30', '40'].map((n) => `onto-${n}`),
    );
    expect(notice()).toBe('12 ontologies enabled.');
  });
});

describe('Workspace settings › Graphs (resource access)', () => {
  it('filters Read and Edit from their columns', async () => {
    mounted = await mount(ResourceAccessEditor, { workspaceId: 'ws-1', kind: 'graphs' });
    await mounted.flush();
    expect([...mounted.host.querySelectorAll('[data-filter-trigger]')].map((th) => th.getAttribute('data-filter-trigger'))).toEqual([
      'name',
      'read',
      'edit',
      'availability',
    ]);
    await filterColumn(mounted, 'read', 'Yes');
    expect(rows()).toEqual(['onto-03', 'onto-04']);
    await filterColumn(mounted, 'edit', 'No');
    expect(rows()).toEqual(['onto-03']);
    expect(mounted.host.textContent).not.toContain('2 readable · 1 editable');
    expect(mounted.host.textContent).toContain('45 graphs');
    // Its options in a section of their own, under the page's title.
    expect([...mounted.host.querySelectorAll('h3')].map((h) => h.textContent)).toContain('Options');
    expect(mounted.host.textContent).not.toContain('Workspace access');
  });

  it('gives the graphs selected Read and edit in one save, and an option at once', async () => {
    mounted = await mount(ResourceAccessEditor, { workspaceId: 'ws-1', kind: 'graphs' });
    await mounted.flush();
    await mounted.click(mounted.host.querySelector('[data-select-row="onto-01"]'));
    await mounted.click(mounted.host.querySelector('[data-select-row="onto-03"]'));
    await mounted.click(mounted.host.querySelector('[data-bulk-action="edit"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Give Read and edit to 2 graphs?');
    await mounted.click(confirmButton('Read and edit'));
    await mounted.flush();
    expect(PUTS[0].policy).toEqual({ read: ['onto-03', 'onto-01'], write: ['onto-04', 'onto-01', 'onto-03'] });
    expect(notice()).toBe('2 graphs: Read and edit.');

    await mounted.click(
      [...mounted.host.querySelectorAll('label')].find((l) => l.textContent === 'Read all graphs, including future graphs')!
        .querySelector('input'),
    );
    await mounted.flush();
    expect(PUTS[1]).toMatchObject({ revision: 2, policy: { read_all: true } });
  });
});
