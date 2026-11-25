// @vitest-environment jsdom
import { afterEach, describe, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import { checkPagedTable } from '@/lib/testing/paged-table';

import { FEATURE_SCOPES, WEB_ENGINES } from '@/lib/search-scopes';

const TOPICS = vi.hoisted(() =>
  Array.from({ length: 45 }, (_, i) => {
    const n = String(i + 1).padStart(2, '0');
    return {
      id: `topic-${n}`,
      plural_label: i === 36 ? 'Zebras' : `Topics ${n}`,
      icon: 'search',
      enabled: true,
      source: 'custom',
    };
  }),
);

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: () => undefined }),
  useSearchParams: () => ({ get: () => null }),
  usePathname: () => '/workspace/ws-1/settings/search',
}));
vi.mock('@/stores/search-topics', () => ({
  useSearchTopicsStore: () => ({
    topics: TOPICS,
    disabledScopes: [],
    setDisabledScopes: () => undefined,
    canEdit: true,
    loading: false,
    error: null,
    load: async () => undefined,
    replace: () => undefined,
    remove: () => undefined,
  }),
}));
vi.mock('@/stores/workspace', () => ({
  useWorkspaceStore: (select: (state: unknown) => unknown) => select({ getCurrentWorkspace: () => null }),
}));
vi.mock('@/stores/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/stores/auth')>()),
  authFetch: async () => new Response('[]', { status: 200 }),
}));
vi.mock('@/lib/search-topics-api', () => ({
  TopicApiError: class extends Error {},
  topicsApi: { contract: async () => ({}) },
}));

import SearchSettingsPage from './page';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Search', () => {
  it('shows 20 entries a page, searches and filters all of them, back to the first page', async () => {
    mounted = await mount(SearchSettingsPage, {});
    await mounted.flush();
    await checkPagedTable(mounted, {
      row: 'data-entry',
      // Topics, then the Nexus features and the web engines.
      total: 45 + FEATURE_SCOPES.length + WEB_ENGINES.length,
      search: 'input[placeholder="Search topics, features and engines..."]',
      far: { id: 'topic-37', query: 'zebras' },
      filter: { select: 'select[aria-label="Group"]', value: 'Custom' },
    });
  });
});
