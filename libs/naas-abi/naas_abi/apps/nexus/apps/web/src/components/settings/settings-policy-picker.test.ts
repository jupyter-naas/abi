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
import { useFeaturesSubgroup } from './features-subgroup';

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
  NAV.path = '/workspace/ws-1/settings/datasets';
  usePolicyViewStore.setState({ views: {} });
  useFeaturesSubgroup.setState({ open: false });
});

const hrefs = (m: Mounted) => [...m.host.querySelectorAll('nav a')].map((a) => a.getAttribute('href'));

describe('the Policy picker of a workspace’s Settings column', () => {
  it('hangs under Access › Features with the Features pages, folded by default, its toggle at the row\'s right', async () => {
    NAV.path = '/workspace/ws-1/settings/users';
    usePolicyViewStore.setState({
      views: { 'ws-1|': { status: 'ready', state: state(ACCESS, [row('agents', 'everyone'), row('datasets', 'everyone')]) } },
    });
    mounted = await mount(SettingsLevelsNav, { level: LEVEL });
    await mounted.flush();
    // No Features heading any more: its pages are Access › Features' sub-group, folded.
    expect([...mounted.host.querySelectorAll('h2')].map((h) => h.textContent)).toEqual(['Access']);
    expect(mounted.host.querySelector('[data-policy-picker]')).toBeNull();
    expect(hrefs(mounted)).toEqual([
      '/workspace/ws-1/settings/users',
      '/workspace/ws-1/settings/features',
      '/workspace/ws-1/settings/modules',
    ]);
    const toggle = mounted.host.querySelector('a[href="/workspace/ws-1/settings/features"] + button[data-action="subgroup"]')!;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    await mounted.click(toggle);
    const picker = mounted.host.querySelector('[data-features-subgroup] [data-policy-picker]');
    expect(picker?.textContent).toContain('Alpha access');
    expect(hrefs(mounted)).toEqual([
      '/workspace/ws-1/settings/users',
      '/workspace/ws-1/settings/features',
      // The sub-group, under Access › Features.
      '/workspace/ws-1/settings/agents',
      '/workspace/ws-1/settings/datasets',
      '/workspace/ws-1/settings/files',
      '/workspace/ws-1/settings/workflows',
      '/workspace/ws-1/settings/modules',
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
    // A page of the sub-group open: it unfolds by itself (a Configure link of Access › Features).
    expect(mounted.host.querySelector('[data-features-subgroup] [data-policy-picker]')?.textContent).toContain('Analysts grants');
    expect(hrefs(mounted)).toEqual([
      '/workspace/ws-1/settings/users',
      '/workspace/ws-1/settings/features?policy=pol_g',
      '/workspace/ws-1/settings/datasets?policy=pol_g',
      // Workflows shows no feature: module items, set in Access › Modules.
      '/workspace/ws-1/settings/workflows?policy=pol_g',
      '/workspace/ws-1/settings/modules?policy=pol_g',
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
