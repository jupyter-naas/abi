// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const state = vi.hoisted(() => ({
  path: '/workspace/ws-1/settings/general',
  settingsByRole: false,
  access: null as null | { actions: Record<string, boolean> },
  replaced: [] as string[],
  mobile: false,
}));

vi.mock('next/navigation', () => ({
  usePathname: () => state.path,
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({
    replace: (to: string) => state.replaced.push(to),
    push: () => undefined,
    prefetch: () => undefined,
  }),
}));
vi.mock('@/components/settings/settings-levels-nav', () => ({ SettingsLevelsNav: () => 'SETTINGS COLUMN' }));
vi.mock('@/hooks/use-settings-levels', () => ({ useSettingsTabs: () => ({ tabs: [], level: null }) }));
vi.mock('@/hooks/use-is-mobile', () => ({ useIsMobile: () => state.mobile }));
vi.mock('@/hooks/use-dev-route-warmup', () => ({ useDevRouteWarmup: () => undefined }));
vi.mock('@/hooks/use-workspace-resources', () => ({
  useWorkspaceResources: () => ({ status: 'ready', resources: null }),
  reloadWorkspaceResources: async () => undefined,
}));
vi.mock('@/hooks/use-feature', () => ({ useFeature: () => state.settingsByRole }));
vi.mock('@/lib/iam-admin/use-access', () => ({
  useIamAccess: () => ({ access: state.access, loading: false, error: null, can: () => false }),
}));
vi.mock('@/stores/workspace', () => {
  const store = {
    workspaces: [{ id: 'ws-1', name: 'Alpha', organizationId: 'acme' }],
    currentWorkspaceId: 'ws-1',
    fetchWorkspaces: async () => undefined,
  };
  return { useWorkspaceStore: (select: (s: typeof store) => unknown) => select(store) };
});

import { createElement } from 'react';
import { settingsLevelReturnPath, settingsReturnPath } from '@/lib/settings-scope-path';
import SettingsLayout from './layout';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  state.replaced = [];
  state.mobile = false;
  state.path = '/workspace/ws-1/settings/general';
  window.sessionStorage.clear();
});

async function render(): Promise<string> {
  mounted = await mount(SettingsLayout, { children: createElement('p', null, 'GENERAL PAGE') });
  await mounted.flush();
  return mounted.host.textContent ?? '';
}

describe('workspace settings by URL (UJ-W1)', () => {
  it('show the page to an owner or admin (the role brings the settings), beside the Settings column', async () => {
    state.settingsByRole = true;
    state.access = null;
    const text = await render();
    expect(text).toContain('GENERAL PAGE');
    expect(text).toContain('SETTINGS COLUMN');
    expect(text).toContain('Settings');
    expect(mounted?.host.querySelector('header [aria-label="Help"]')).not.toBeNull();
    expect(mounted?.host.querySelector('header [aria-label="Log out"]')).not.toBeNull();
  });

  it('list Settings on a phone at the index, and open one page at a time', async () => {
    state.settingsByRole = true;
    state.mobile = true;
    state.path = '/workspace/ws-1/settings';
    const list = await render();
    expect(list).toContain('SETTINGS COLUMN');
    expect(list).not.toContain('GENERAL PAGE');
    await mounted?.unmount();
    state.path = '/workspace/ws-1/settings/general';
    const page = await render();
    expect(page).not.toContain('SETTINGS COLUMN');
    expect(page).toContain('GENERAL PAGE');
    expect(page).toContain('General');
    state.mobile = false;
  });

  it('refuse a member with no settings and no iam: right there (Dave)', async () => {
    state.settingsByRole = false;
    state.access = { actions: { 'iam:ListPolicies': false } };
    const text = await render();
    expect(text).not.toContain('GENERAL PAGE');
    expect(text).toContain('You have no access to these settings');
  });

  it('send someone holding only iam: rights there to the first Access page they hold', async () => {
    state.settingsByRole = false;
    state.access = { actions: { 'iam:ListPolicies': true } };
    const text = await render();
    expect(text).not.toContain('GENERAL PAGE');
    expect(state.replaced).toEqual(['/workspace/ws-1/settings/policies']);
    for (const path of ['/workspace/ws-1/settings/policies', '/workspace/ws-1/settings/policies/pol_1', '/workspace/ws-1/settings/members/usr_bob']) {
      state.path = path;
      await mounted?.unmount();
      mounted = null;
      expect(await render()).toContain('GENERAL PAGE');
    }
    state.path = '/workspace/ws-1/settings/general';
  });

  it('send someone IAM lets list only the groups there to Groups, never to Policies', async () => {
    state.settingsByRole = false;
    state.access = { actions: { 'iam:ListGroups': true } };
    await render();
    expect(state.replaced).toEqual(['/workspace/ws-1/settings/groups']);
    state.replaced = [];
    state.path = '/workspace/ws-1/settings/policies';
    await mounted?.unmount();
    mounted = null;
    await render();
    expect(state.replaced).toEqual(['/workspace/ws-1/settings/groups']);
    state.path = '/workspace/ws-1/settings/general';
  });
});

describe('the workspace settings page Settings reopens', () => {
  it('is remembered once the page opens, never when it is refused or sends the caller elsewhere', async () => {
    state.settingsByRole = false;
    state.access = { actions: { 'iam:ListPolicies': false } };
    expect(await render()).toContain('You have no access to these settings');
    expect(settingsReturnPath('nothing')).toBe('nothing');

    await mounted?.unmount();
    state.access = { actions: { 'iam:ListPolicies': true } };
    await render();
    expect(state.replaced).toEqual(['/workspace/ws-1/settings/policies']);
    expect(settingsReturnPath('nothing')).toBe('nothing');

    await mounted?.unmount();
    state.settingsByRole = true;
    expect(await render()).toContain('GENERAL PAGE');
    expect(settingsReturnPath('nothing')).toBe('/workspace/ws-1/settings/general');
    expect(settingsLevelReturnPath('workspace')).toBe('/workspace/ws-1/settings/general');
  });

  it('is not the index', async () => {
    state.settingsByRole = true;
    state.path = '/workspace/ws-1/settings';
    await render();
    expect(settingsReturnPath('nothing')).toBe('nothing');
  });
});
