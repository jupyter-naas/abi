// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

const SNAPSHOT = vi.hoisted(() => ({
  data: { enabled: [] },
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
  authFetch: async () => new Response(JSON.stringify(SNAPSHOT), { status: 200 }),
}));
vi.mock('@/stores/graph-explorer', () => ({ invalidateGraphExplorer: () => undefined }));
vi.mock('@/stores/ontology', () => ({ useOntologyStore: { setState: () => undefined } }));

import { ResourceAccessEditor } from './resource-access';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Ontologies (resource access)', () => {
  it('shows 20 rows a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(ResourceAccessEditor, { workspaceId: 'ws-1', kind: 'ontologies' });
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-resource',
      total: 45,
      search: 'input[placeholder="Search ontologies…"]',
      far: { id: 'onto-37', query: 'zebra' },
      filter: { select: 'select[aria-label="Availability"]', value: 'available' },
    });
  });
});
