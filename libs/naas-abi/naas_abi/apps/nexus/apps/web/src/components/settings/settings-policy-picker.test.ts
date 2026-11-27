// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Bot, Database, Files, Package, SlidersHorizontal, Users, Workflow } from 'lucide-react';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { FeatureAccessState } from '@/app/workspace/[workspaceId]/settings/features/feature-access-model';
import type { SettingsLevel } from './settings-levels';

const NAV = vi.hoisted(() => ({
  path: '/workspace/ws-1/settings/datasets',
  policy: null as string | null,
  pushed: [] as string[],
}));
vi.mock('next/navigation', () => ({
  usePathname: () => NAV.path,
  useSearchParams: () => ({ get: (key: string) => (key === 'policy' ? NAV.policy : null) }),
  useRouter: () => ({ push: (to: string) => NAV.pushed.push(to), prefetch: () => undefined, replace: () => undefined }),
}));
// The organization and workspace pickers atop the column are checked on their own.
vi.mock('./settings-scope-switcher', () => ({ SettingsScopeSwitcher: () => null }));

import { SettingsLevelsNav } from './settings-levels-nav';
import { usePolicyViewStore } from './settings-policy-picker';

const WS = 'abi:nexus:organization/acme/nexus:workspace/ws-1';
const ACCESS = { id: 'pol_w', name: 'Alpha access', owner_scope: WS };
const GRANTS = { id: 'pol_g', name: 'Analysts grants', owner_scope: WS };

const row = (key: string, choice: 'everyone' | 'nobody') => ({
  key,
  label: key,
  choice,
  principals: [],
  policy: null,
  hand_edited: false,
  offered: true,
  held: true,
  editable: true,
  reason: null,
  also: [],
});

const state = (policy: typeof ACCESS, rows: ReturnType<typeof row>[]): FeatureAccessState => ({
  workspace_id: 'ws-1',
  scope: WS,
  access_policy: ACCESS,
  policy,
  policies: [ACCESS, GRANTS],
  members_group: null,
  can: { create: true, attach: true, detach: true, widen: true },
  features: rows,
});

const link = (page: string, label: string, icon = Bot) => ({ href: `/workspace/ws-1/settings/${page}`, label, icon });
const LEVEL: SettingsLevel = {
  id: 'workspace',
  label: 'Workspace',
  index: '/workspace/ws-1/settings',
  groups: [
    { label: null, links: [link('users', 'Users', Users)] },
    { label: 'Access', links: [link('features', 'Features', SlidersHorizontal), link('modules', 'Modules', Package)] },
    {
      label: 'Features',
      links: [
        link('agents', 'Agents'),
        link('datasets', 'Datasets', Database),
        link('files', 'Files', Files),
        link('workflows', 'Workflows', Workflow),
      ],
    },
  ],
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  NAV.policy = null;
  NAV.pushed = [];
  usePolicyViewStore.setState({ views: {} });
});

const hrefs = (m: Mounted) => [...m.host.querySelectorAll('nav a')].map((a) => a.getAttribute('href'));

describe('the Policy picker of a workspace’s Settings column', () => {
  it('sits under the Features heading, "<W> access" picked, and the links stay as they are', async () => {
    usePolicyViewStore.setState({
      views: { 'ws-1|': { status: 'ready', state: state(ACCESS, [row('agents', 'everyone'), row('datasets', 'everyone')]) } },
    });
    mounted = await mount(SettingsLevelsNav, { level: LEVEL });
    await mounted.flush();
    const picker = mounted.host.querySelector('[data-policy-picker]');
    expect(picker?.textContent).toContain('Alpha access');
    // Under the Features heading, in its group.
    expect(picker?.closest('.settings-level-group')?.querySelector('h2')?.textContent).toBe('Features');
    expect(hrefs(mounted)).toEqual([
      '/workspace/ws-1/settings/users',
      '/workspace/ws-1/settings/features',
      '/workspace/ws-1/settings/modules',
      '/workspace/ws-1/settings/agents',
      '/workspace/ws-1/settings/datasets',
      '/workspace/ws-1/settings/files',
      '/workspace/ws-1/settings/workflows',
    ]);
  });

  it('with another policy picked, the Access and Features links carry it, and Features lists what it grants', async () => {
    NAV.policy = 'pol_g';
    usePolicyViewStore.setState({
      views: {
        'ws-1|pol_g': {
          status: 'ready',
          state: state(GRANTS, [row('agents', 'nobody'), row('datasets', 'everyone'), row('files', 'nobody')]),
        },
      },
    });
    mounted = await mount(SettingsLevelsNav, { level: LEVEL });
    await mounted.flush();
    expect(mounted.host.querySelector('[data-policy-picker]')?.textContent).toContain('Analysts grants');
    expect(hrefs(mounted)).toEqual([
      '/workspace/ws-1/settings/users',
      '/workspace/ws-1/settings/features?policy=pol_g',
      '/workspace/ws-1/settings/modules?policy=pol_g',
      '/workspace/ws-1/settings/datasets?policy=pol_g',
      // Workflows shows no feature: module items, set in Access › Modules.
      '/workspace/ws-1/settings/workflows?policy=pol_g',
    ]);
    // The page open stays marked, its link carrying the policy.
    expect(mounted.host.querySelector('nav a[aria-current="page"]')?.getAttribute('href')).toBe(
      '/workspace/ws-1/settings/datasets?policy=pol_g'
    );
  });

  it('reads the policies once per workspace and policy', async () => {
    const read = vi.fn().mockResolvedValue(state(ACCESS, []));
    usePolicyViewStore.getState().load('ws-2', null, { read, save: vi.fn() });
    usePolicyViewStore.getState().load('ws-2', null, { read, save: vi.fn() });
    await Promise.resolve();
    expect(read).toHaveBeenCalledTimes(1);
    expect(read).toHaveBeenCalledWith('ws-2', null);
    usePolicyViewStore.getState().forget('ws-2');
    expect(usePolicyViewStore.getState().views['ws-2|']).toBeUndefined();
  });
});
