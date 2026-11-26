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
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  authFetch: async (url: string) =>
    new Response(
      JSON.stringify(
        url.endsWith('/graphs')
          ? { ...SNAPSHOT, data: { read: ['onto-03'], write: ['onto-04'] } }
          : SNAPSHOT,
      ),
      { status: 200 },
    ),
}));
vi.mock('@/stores/graph-explorer', () => ({ invalidateGraphExplorer: () => undefined }));
vi.mock('@/stores/ontology', () => ({ useOntologyStore: { setState: () => undefined } }));

import { ResourceAccessEditor } from './resource-access';
import { pickColumnFilter as filterColumn } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

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
    expect(mounted.host.textContent).toContain('1 of 45 ontologies');
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
    // The filter reads the draft: a row unticked under it leaves the table.
    await mounted.click(mounted.host.querySelector('[aria-label="Enable Ontology 02"]'));
    expect(rows()).toEqual([]);
    expect(mounted.host.textContent).toContain('No ontologies match the current search and filters');
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
    expect(mounted.host.textContent).toContain('2 readable · 1 editable');
  });
});
