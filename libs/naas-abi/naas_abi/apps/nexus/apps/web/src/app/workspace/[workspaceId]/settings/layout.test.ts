// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const state = vi.hoisted(() => ({
  path: '/workspace/ws-1/settings/general',
  settingsByRole: false,
  access: null as null | { actions: Record<string, boolean> },
  replaced: [] as string[],
}));

vi.mock('next/navigation', () => ({
  usePathname: () => state.path,
  useParams: () => ({ workspaceId: 'ws-1' }),
  useRouter: () => ({ replace: (to: string) => state.replaced.push(to), push: () => undefined }),
}));
vi.mock('@/components/shell/header', () => ({ Header: () => null }));
vi.mock('@/hooks/use-dev-route-warmup', () => ({ useDevRouteWarmup: () => undefined }));
vi.mock('@/hooks/use-workspace-resources', () => ({
  useWorkspaceResources: () => ({ resources: null }),
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
import SettingsLayout from './layout';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  state.replaced = [];
});

async function render(): Promise<string> {
  mounted = await mount(SettingsLayout, { children: createElement('p', null, 'GENERAL PAGE') });
  await mounted.flush();
  return mounted.host.textContent ?? '';
}

describe('workspace settings by URL (UJ-W1)', () => {
  it('show the page to an owner or admin (the role brings the settings)', async () => {
    state.settingsByRole = true;
    state.access = null;
    expect(await render()).toContain('GENERAL PAGE');
  });

  it('refuse a member with no settings and no iam: right there (Dave)', async () => {
    state.settingsByRole = false;
    state.access = { actions: { 'iam:ListPolicies': false } };
    const text = await render();
    expect(text).not.toContain('GENERAL PAGE');
    expect(text).toContain('You have no access to these settings');
  });

  it('send someone holding only iam: rights there to Roles & permissions', async () => {
    state.settingsByRole = false;
    state.access = { actions: { 'iam:ListPolicies': true } };
    const text = await render();
    expect(text).not.toContain('GENERAL PAGE');
    expect(state.replaced).toEqual(['/workspace/ws-1/settings/permissions']);
    state.path = '/workspace/ws-1/settings/permissions';
    await mounted?.unmount();
    mounted = null;
    expect(await render()).toContain('GENERAL PAGE');
    state.path = '/workspace/ws-1/settings/general';
  });
});
