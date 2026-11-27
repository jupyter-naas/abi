// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

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

const NAV = vi.hoisted(() => ({ policy: null as string | null }));
vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ push: () => undefined }),
  useSearchParams: () => ({ get: (key: string) => (key === 'policy' ? NAV.policy : null) }),
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
const API = vi.hoisted(() => ({
  save: vi.fn(async (_ws: string, topic: Record<string, unknown>) => topic),
  setScopeEnabled: vi.fn(async () => ({ disabled_scopes: [] })),
}));
vi.mock('@/lib/search-topics-api', () => ({
  TopicApiError: class extends Error {},
  topicsApi: { contract: async () => ({}), ...API },
}));

import SearchSettingsPage from './page';
import { pickColumnFilter as filterColumn } from '@/lib/testing/column-filter';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('Workspace settings › Search', () => {
  const total = 45 + FEATURE_SCOPES.length + WEB_ENGINES.length;
  const rows = () => [...mounted!.host.querySelectorAll('[data-entry]')].map((r) => r.getAttribute('data-entry'));
  const shown = () => mounted!.host.querySelector('[data-field="rows-shown"]')?.textContent;
  const search = () => mounted!.host.querySelector('input[placeholder="Search topics, features and engines..."]');

  it('shows 20 entries a page, searches all of them, topics first', async () => {
    mounted = await mount(SearchSettingsPage, {});
    await mounted.flush();
    expect(rows()).toHaveLength(20);
    expect(rows()[0]).toBe('topic-01');
    expect(shown()).toBe(`Rows 1–20 of ${total}`);
    expect(rows()).not.toContain('topic-37');
    await mounted.click(mounted.host.querySelector('[data-action="next-page"]'));
    expect(shown()).toBe(`Rows 21–40 of ${total}`);

    await mounted.type(search(), 'zebras');
    expect(rows()).toEqual(['topic-37']);
    // One total in the badge, no count above the search.
    expect(mounted.host.textContent).toContain(`${total} entries`);
    expect(mounted.host.textContent).not.toContain(`1 of ${total} entries`);
  });

  it('filters on a column (Group and Enabled replace the dropdowns) and goes back to the first page', async () => {
    mounted = await mount(SearchSettingsPage, {});
    await mounted.flush();
    expect(mounted.host.querySelector('select[aria-label="Group"]')).toBeNull();
    await mounted.click(mounted.host.querySelector('[data-action="next-page"]'));
    expect(shown()).toMatch(/^Rows 21–/);

    await filterColumn(mounted, 'group', 'Custom');
    expect(shown()).toBe('Rows 1–20 of 45');

    await mounted.click(mounted.host.querySelector('[data-action="clear-filters"]'));
    expect(shown()).toBe(`Rows 1–20 of ${total}`);
    await filterColumn(mounted, 'group', 'Web');
    expect(rows()).toEqual(WEB_ENGINES.map((engine) => `web.${engine.id}`));

    await mounted.click(mounted.host.querySelector('[data-action="clear-filters"]'));
    // Features of a workspace that is not loaded are off: Disabled lists them.
    await filterColumn(mounted, 'enabled', 'Disabled');
    expect(rows()).toEqual(FEATURE_SCOPES.map((scope) => scope.id));
  });

  it('switches a source on the policy picked in the Settings column', async () => {
    NAV.policy = 'pol_g';
    try {
      mounted = await mount(SearchSettingsPage, {});
      await mounted.flush();
      await filterColumn(mounted, 'group', 'Web');
      const engine = WEB_ENGINES[0];
      // The policy grants no source yet: the engine is off, and switching it writes the policy.
      const box = mounted.host.querySelector(`[aria-label="${engine.label} enabled"]`) as HTMLInputElement;
      expect(box.checked).toBe(false);
      await mounted.click(box);
      await mounted.flush();
      expect(API.setScopeEnabled).toHaveBeenCalledWith('ws-1', `web.${engine.id}`, true, 'pol_g');
    } finally {
      NAV.policy = null;
    }
  });

  it('disables the entries selected in one step, asked first; a feature not available here is not selected', async () => {
    mounted = await mount(SearchSettingsPage, {});
    await mounted.flush();
    await mounted.click(mounted.host.querySelector('[data-select-row="topic-01"]'));
    await mounted.click(mounted.host.querySelector('[data-select-row="topic-02"]'));
    await mounted.click(mounted.host.querySelector('[data-bulk-action="off"]'));
    expect(document.querySelector('[data-bulk-confirm]')?.textContent).toContain('Disable 2 entries?');
    const confirm = [...document.querySelectorAll<HTMLButtonElement>('[data-bulk-confirm] button')].find(
      (b) => b.textContent === 'Disable',
    )!;
    await mounted.click(confirm);
    await mounted.flush();
    expect(API.save.mock.calls.map(([, topic]) => [topic.id, topic.enabled])).toEqual([
      ['topic-01', false],
      ['topic-02', false],
    ]);
    expect(mounted.host.querySelector('[data-search-notice]')?.textContent).toBe('2 entries disabled.');
    // Features of a workspace that is not loaded are off: their boxes are disabled.
    await filterColumn(mounted, 'group', 'Workspace');
    const feature = mounted.host.querySelector(`[data-select-row="${FEATURE_SCOPES[0].id}"]`) as HTMLInputElement;
    expect(feature.disabled).toBe(true);
  });
});
