// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

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

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Apps', () => {
  it('shows 20 apps a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(AppsSettingsPage, {});
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-app',
      total: 45,
      search: 'input[placeholder="Search apps..."]',
      far: { id: 'app-37', query: 'zebra' },
      filter: { select: 'select[aria-label="Category"]', value: 'core' },
    });
  });
});
