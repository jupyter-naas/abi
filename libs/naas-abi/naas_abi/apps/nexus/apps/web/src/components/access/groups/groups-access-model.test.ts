// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CapabilityView } from '@/lib/iam-admin/types';
import { mount, type Mounted } from '@/lib/testing/mount';
import { EMPTY_DIRECTORY } from '../access-directory';
import { WS, orgScope } from '../access-fixtures';
import { allowAll, fakeApi, group } from '../service-fixtures';
import { GroupsView } from './groups';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

const ORG = 'abi:nexus:organization/acme';

const groups = [
  group({ id: 'grp_custom', name: 'Data team', owner_scope: ORG }),
  group({ id: 'grp_runners', name: 'Workflow runners', owner_scope: ORG }),
  group({ id: 'grp_ws', name: 'Sales workspace', owner_scope: WS, membership_of: WS }),
  group({ id: 'grp_wsadmins', name: 'Sales admins', owner_scope: WS }),
  group({ id: 'grp_admins', name: 'Acme admins', owner_scope: ORG }),
  group({ id: 'grp_members', name: 'Members', owner_scope: 'abi:', level_group: true }),
];

const runners = (over: Partial<CapabilityView> = {}): CapabilityView => ({
  capability: 'workflow_runners',
  name: 'Workflow runners',
  owner_scope: ORG,
  group_id: null,
  policy_id: null,
  can_create: true,
  ...over,
});

function api(capabilities: CapabilityView[]) {
  return fakeApi({
    listGroups: vi.fn(() => Promise.resolve({ items: groups })),
    getGroup: vi.fn((id: string) => Promise.resolve(group({ id, members: [] }))),
    capabilities: vi.fn(() => Promise.resolve({ scope: ORG, capabilities })),
    ensureCapability: vi.fn(() => Promise.resolve(runners({ group_id: 'grp_runners', can_create: false }))),
  });
}

async function open(client: ReturnType<typeof api>) {
  mounted = await mount(GroupsView, { api: client, can: allowAll, scope: orgScope, directory: EMPTY_DIRECTORY });
  await mounted.flush();
}

describe('Groups first: the model’s groups, then the custom ones', () => {
  it('lists levels, admins, workspaces and capabilities before custom groups, each with its kind', async () => {
    await open(api([]));
    const rows = [...document.querySelectorAll('[data-group]')].map((r) => [
      r.getAttribute('data-group'),
      r.querySelector('[data-group-kind]')?.textContent,
    ]);
    expect(rows).toEqual([
      ['grp_members', 'Level'],
      ['grp_admins', 'Org admins'],
      ['grp_wsadmins', 'Workspace admins'],
      ['grp_ws', 'Workspace'],
      ['grp_runners', 'Capability'],
      ['grp_custom', 'Custom'],
    ]);
  });

  it('shows the generic level policies read-only, with what each grants', async () => {
    await open(api([]));
    const levels = document.querySelector('[data-access-levels]');
    expect([...levels!.querySelectorAll('[data-level]')].map((l) => l.getAttribute('data-level'))).toEqual([
      'viewer',
      'member',
      'admin',
    ]);
    expect(levels?.querySelector('[data-level="viewer"]')?.textContent).toContain('No model');
    expect(levels?.querySelector('button')).toBeNull();
  });
});

describe('capability groups', () => {
  it('creates Workflow runners on demand where the caller may', async () => {
    const client = api([runners()]);
    await open(client);
    const row = document.querySelector('[data-capability="workflow_runners"]');
    expect(row?.textContent).toContain('not made yet');
    await mounted!.click(row?.querySelector('[data-action="create-capability"]') ?? null);
    await mounted!.flush();
    expect(client.ensureCapability).toHaveBeenCalledWith('workflow_runners', ORG);
  });

  it('opens one already made, and offers no create to whoever may not', async () => {
    const client = api([runners({ group_id: 'grp_runners', can_create: false })]);
    await open(client);
    const row = document.querySelector('[data-capability="workflow_runners"]');
    expect(row?.querySelector('[data-action="create-capability"]')).toBeNull();
    await mounted!.click(row?.querySelector('button') ?? null);
    await mounted!.flush();
    expect(document.querySelector('[data-capability]')).toBeNull(); // the group's page is open
  });

  it('leaves the section out when the caller may not list them', async () => {
    const client = api([]);
    client.capabilities = vi.fn(() => Promise.reject(new Error('403')));
    await open(client);
    expect(document.querySelector('[data-capabilities]')).toBeNull();
    expect(document.querySelector('[data-access-levels]')).not.toBeNull();
  });
});
