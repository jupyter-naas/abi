// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const PERMISSIONS = vi.hoisted(() => ({ data: null, error: null, find: () => undefined, names: new Map() }));
const NAV = vi.hoisted(() => ({ feed: null as string | null }));
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

const LAYERS = vi.hoisted(() =>
  ['Roads', 'Bridges', 'Ports'].map((title, i) => ({
    id: `feed-01-${title.toLowerCase()}`,
    feed_id: 'feed-01',
    title,
    description: '',
    color: '#336699',
    icon: '',
    order: 3 - i,
    class_labels: i === 2 ? [] : [title],
  })),
);

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: () => undefined }),
  useSearchParams: () => ({ get: (key: string) => (key === 'feed' ? NAV.feed : null) }),
  usePathname: () => '/workspace/ws-1/settings/maps',
}));
vi.mock('@/stores/maps', () => ({
  useMapsStore: (select: (state: unknown) => unknown) =>
    select({ applyLayouts: () => undefined, loadLayouts: async () => undefined }),
}));
vi.mock('@/app/workspace/[workspaceId]/maps/lib/use-map-layouts', () => ({
  useMapLayers: () => ({
    all: [],
    hidden: ['feed-01-roads'],
    hiddenFeeds: ['feed-02'],
    canEdit: true,
    workspaceLayouts: FEEDS,
    feedLayers: LAYERS,
    loading: false,
    error: null,
    layerGroups: [],
  }),
}));
vi.mock('@/app/workspace/[workspaceId]/maps/components/maps-settings-access', () => ({
  MapsAccessCell: () => null,
  useMapsPermissions: () => PERMISSIONS,
}));
// A feed's page: only its Layers table is checked here.
vi.mock('@/app/workspace/[workspaceId]/maps/components/maps-layer-editor-form', () => ({
  MapsLayerEditorForm: () => null,
}));
vi.mock('@/app/workspace/[workspaceId]/maps/components/maps-feed-layer-form', () => ({
  MapsFeedLayerForm: () => null,
  slugifyLayerId: (id: string) => id,
  useFeedTypes: () => ({ types: [] }),
}));
vi.mock('@/app/workspace/[workspaceId]/maps/components/maps-settings-basemaps-section', () => ({
  MapsSettingsBasemapsSection: () => null,
}));

import MapsSettingsPage from './page';
import { pickColumnFilter as filterColumn } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const attr = (name: string) => [...mounted!.host.querySelectorAll(`[${name}]`)].map((r) => r.getAttribute(name));
const shown = () => mounted!.host.querySelector('[data-field="rows-shown"]')?.textContent;

describe('Workspace settings › Maps', () => {
  afterEach(() => {
    NAV.feed = null;
  });

  it('shows 20 feeds a page, by group, and searches all of them', async () => {
    mounted = await mount(MapsSettingsPage, {});
    await mounted.flush();
    expect(attr('data-feed')).toHaveLength(20);
    expect(attr('data-feed')[0]).toBe('feed-01');
    expect(shown()).toBe('Rows 1–20 of 45');
    expect(attr('data-feed')).not.toContain('feed-37');
    await mounted.click(mounted.host.querySelector('[data-action="next-page"]'));
    expect(shown()).toBe('Rows 21–40 of 45');

    await mounted.type(mounted.host.querySelector('input[placeholder="Search feeds…"]'), 'zebra');
    expect(attr('data-feed')).toEqual(['feed-37']);
    // One total in the badge, no count above the search.
    expect(mounted.host.textContent).toContain('45 feeds');
    expect(mounted.host.textContent).not.toContain('1 of 45 feeds');
    expect(mounted.host.textContent).not.toContain(' shown');
  });

  it('filters Group and Enabled from their columns, back to the first page; bulk actions follow', async () => {
    mounted = await mount(MapsSettingsPage, {});
    await mounted.flush();
    expect(mounted.host.querySelector('select[aria-label="Group"]')).toBeNull();
    await mounted.click(mounted.host.querySelector('[data-action="next-page"]'));

    await filterColumn(mounted, 'group', 'Places');
    expect(shown()).toBe('Rows 1–20 of 41');
    await mounted.click(mounted.host.querySelector('[data-action="clear-filters"]'));

    await filterColumn(mounted, 'enabled', 'Disabled');
    expect(attr('data-feed')).toEqual(['feed-02']);
    expect(mounted.host.textContent).toContain('Enable (1)');
    expect(mounted.host.textContent).not.toContain('Disable (');
  });

  it("a feed's Layers table: by order, filtered from its columns", async () => {
    NAV.feed = 'feed-01';
    mounted = await mount(MapsSettingsPage, {});
    await mounted.flush();
    expect(attr('data-layer')).toEqual(['feed-01-ports', 'feed-01-bridges', 'feed-01-roads']);
    expect(mounted.host.textContent).toContain('Every feature');

    await filterColumn(mounted, 'shown', 'Hidden');
    expect(attr('data-layer')).toEqual(['feed-01-roads']);
    await mounted.click(mounted.host.querySelector('[data-action="clear-filters"]'));
    await mounted.type(mounted.host.querySelector('input[placeholder="Search layers…"]'), 'bridges');
    expect(attr('data-layer')).toEqual(['feed-01-bridges']);
    expect(mounted.host.textContent).not.toContain('1 of 3 layers');
  });
});
