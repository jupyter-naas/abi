// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

const FEEDS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      id: `feed-${n}`,
      title: i === 36 ? 'Zebra sightings' : `Feed ${n}`,
      // The last four are assets: the "Places" group keeps 41.
      group: i < 41 ? 'Places' : 'Assets',
      feed_type: 'sparql',
    };
  }),
);

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: () => undefined }),
  useSearchParams: () => ({ get: () => null }),
  usePathname: () => '/workspace/ws-1/settings/maps',
}));
vi.mock('@/stores/maps', () => ({
  useMapsStore: (select: (state: unknown) => unknown) =>
    select({ applyLayouts: () => undefined, loadLayouts: async () => undefined }),
}));
vi.mock('@/app/workspace/[workspaceId]/maps/lib/use-map-layouts', () => ({
  useMapLayers: () => ({
    all: [],
    hidden: [],
    hiddenFeeds: [],
    canEdit: true,
    workspaceLayouts: FEEDS,
    feedLayers: [],
    loading: false,
    error: null,
    layerGroups: [],
  }),
}));
vi.mock('@/app/workspace/[workspaceId]/maps/components/maps-settings-access', () => ({
  MapsAccessCell: () => null,
  useMapsPermissions: () => ({ data: null, error: null }),
}));
vi.mock('@/app/workspace/[workspaceId]/maps/components/maps-settings-basemaps-section', () => ({
  MapsSettingsBasemapsSection: () => null,
}));

import MapsSettingsPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Maps', () => {
  it('shows 20 feeds a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(MapsSettingsPage, {});
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-feed',
      total: 45,
      search: 'input[placeholder="Search feeds…"]',
      far: { id: 'feed-37', query: 'zebra' },
      filter: { select: 'select[aria-label="Group"]', value: 'Places' },
    });
  });
});
