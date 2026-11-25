// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

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

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Workflows', () => {
  it('shows 20 items a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(WorkflowsSettingsPage, {});
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-workflow',
      total: 45,
      search: 'input[placeholder="Search workflows..."]',
      far: { id: 'workflow/acme.people/flow-37', query: 'zebra' },
      filter: { select: 'select[aria-label="Type"]', value: 'workflow' },
    });
  });
});
