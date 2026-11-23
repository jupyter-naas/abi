// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { CapabilityGroup, CreatedPerson, PeopleApi } from '@/lib/people';

// The identity providers the form reads (one: nothing to pick).
vi.mock('@/stores/auth', () => ({
  authFetch: async () =>
    new Response(
      JSON.stringify({
        enabled: true,
        default_provider: 'builtin',
        providers: [{ name: 'builtin', display_name: 'Built-in', provisioning: 'builtin', managed_in_provider: false }],
      }),
      { status: 200 }
    ),
}));

import { CreateUserForm, type CreateUserFormProps } from './create-user-form';

const CREATED: CreatedPerson = {
  user: { id: 'usr_bob', email: 'bob@example.com', name: 'Bob', status: 'invited' },
  member: null,
  provider: null,
  emailSent: true,
  warning: null,
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  document.body.innerHTML = '';
});

function fakeApi() {
  const createInWorkspace = vi.fn(async () => CREATED);
  const createInOrganization = vi.fn(async () => CREATED);
  return { createInWorkspace, createInOrganization } satisfies Pick<PeopleApi, 'createInWorkspace' | 'createInOrganization'>;
}

const RUNNERS: CapabilityGroup = {
  id: 'grp_runners',
  name: 'Workflow runners',
  description: null,
  owner_scope: 'abi:nexus:organization/org-acme',
  scope: 'organization',
};

const WORKSPACES = [
  { id: 'ws-b', name: 'Beta' },
  { id: 'ws-a', name: 'Alpha' },
];

async function render(props: Partial<CreateUserFormProps>) {
  const api = fakeApi();
  const onCreated = vi.fn();
  mounted = await mount(CreateUserForm, {
    organization: { fixed: { id: 'org-acme', name: 'Acme' } },
    organizationRoute: false,
    subtitle: 'Create',
    back: { href: '/back', label: 'Back' },
    onCreated,
    onCancel: () => undefined,
    api,
    loadWorkspaces: async () => WORKSPACES,
    loadCapabilities: async () => [RUNNERS],
    ...props,
  } as CreateUserFormProps);
  await mounted.flush();
  return { api, onCreated };
}

const field = <T extends Element = HTMLInputElement>(name: string) =>
  mounted!.host.querySelector<T & Element>(`[data-field="${name}"]`) as T | null;
const create = async () => {
  await mounted!.click(mounted!.host.querySelector('[data-action="create"]'));
  await mounted!.flush();
};

describe('Create user, from a workspace', () => {
  it('shows the organization read-only, asks no org admin, and is prefilled', async () => {
    await render({ attachedWorkspace: { id: 'ws-research', name: 'Research' }, prefill: { email: 'zoe@other.org' } });
    const org = field<HTMLInputElement>('organization')!;
    expect(org.value).toBe('Acme');
    expect(org.readOnly).toBe(true);
    expect(field('org-admin')).toBeNull();
    expect(field('org-role')).toBeNull();
    expect(mounted!.host.querySelector<HTMLInputElement>('#create-user-email')!.value).toBe('zoe@other.org');
    expect(mounted!.host.querySelector('[data-field="workspace-admin"]')?.textContent).toContain('Admin of Research');
    // The level is the person's, in all their workspaces: the note says so.
    expect(mounted!.host.querySelector('[data-level-note]')?.textContent).toMatch(/all of this person.s workspaces/);
    // No organization workspaces to pick, and no org picture.
    expect(mounted!.host.querySelector('[data-workspace]')).toBeNull();
    expect(mounted!.host.querySelector('.account-profile-avatar-section')).toBeNull();
    // No owner anywhere.
    expect(mounted!.host.textContent).not.toMatch(/owner/i);
  });

  it('joins them to the workspace with a level, the admin toggle and capability groups, in one request', async () => {
    const { api, onCreated } = await render({
      attachedWorkspace: { id: 'ws-research', name: 'Research' },
      prefill: { name: 'Zoé' },
    });
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'zoe@other.org');
    await mounted!.select(field('level'), 'viewer');
    await mounted!.click(mounted!.host.querySelector('[data-capability="grp_runners"]'));
    await create();
    expect(api.createInWorkspace).toHaveBeenCalledTimes(1);
    expect(api.createInWorkspace).toHaveBeenCalledWith('ws-research', {
      email: 'zoe@other.org',
      name: 'Zoé',
      level: 'viewer',
      admin: false,
      capabilities: ['grp_runners'],
      provider: undefined,
      profile: undefined,
    });
    expect(api.createInOrganization).not.toHaveBeenCalled();
    expect(onCreated).toHaveBeenCalledWith(CREATED, expect.objectContaining({ route: 'workspace' }));
  });

  it('makes them the workspace admin, as a Member', async () => {
    const { api } = await render({ attachedWorkspace: { id: 'ws-research', name: 'Research' } });
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'zoe@other.org');
    await mounted!.click(mounted!.host.querySelector('[data-field="workspace-admin"] input[type="checkbox"]'));
    await create();
    expect(api.createInWorkspace).toHaveBeenCalledWith('ws-research', expect.objectContaining({ level: 'member', admin: true }));
  });
});

describe('Create user, from the organization', () => {
  it('creates someone with two workspaces, admin of one, in one request', async () => {
    const { api } = await render({ organizationRoute: true });
    expect([...mounted!.host.querySelectorAll('[data-workspace]')].map((li) => li.getAttribute('data-workspace'))).toEqual([
      'ws-a',
      'ws-b',
    ]);
    await mounted!.click(mounted!.host.querySelector('[data-workspace="ws-a"] input[type="checkbox"]'));
    await mounted!.click(mounted!.host.querySelector('[data-workspace="ws-b"] input[type="checkbox"]'));
    await mounted!.click(mounted!.host.querySelector('[data-workspace="ws-b"] [data-field="workspace-admin"] input[type="checkbox"]'));
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledTimes(1);
    expect(api.createInOrganization).toHaveBeenCalledWith(
      'org-acme',
      expect.objectContaining({
        email: 'bob@example.com',
        level: 'member',
        orgAdmin: false,
        workspaces: [
          { id: 'ws-a', admin: false },
          { id: 'ws-b', admin: true },
        ],
      })
    );
  });

  it('makes an org admin with the toggle', async () => {
    const { api } = await render({ organizationRoute: true });
    await mounted!.click(mounted!.host.querySelector('[data-field="org-admin"] input[type="checkbox"]'));
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledWith('org-acme', expect.objectContaining({ orgAdmin: true }));
  });

  it('refuses a Viewer who administers a workspace', async () => {
    const { api } = await render({ organizationRoute: true });
    await mounted!.click(mounted!.host.querySelector('[data-workspace="ws-a"] input[type="checkbox"]'));
    await mounted!.click(mounted!.host.querySelector('[data-workspace="ws-a"] [data-field="workspace-admin"] input[type="checkbox"]'));
    await mounted!.select(field('level'), 'viewer');
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).not.toHaveBeenCalled();
    expect(mounted!.host.querySelector('[role="alert"]')?.textContent).toMatch(/workspace admin is a Member/);
  });

  it('shows the message the page returns, and empties the form', async () => {
    const { api } = await render({ organizationRoute: true, onCreated: () => 'bob@example.com was added to Acme.' });
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledWith('org-acme', expect.objectContaining({ orgAdmin: false, workspaces: [] }));
    expect(mounted!.host.querySelector('[role="status"]')?.textContent).toBe('bob@example.com was added to Acme.');
    expect(mounted!.host.querySelector<HTMLInputElement>('#create-user-email')!.value).toBe('');
  });

  it('lets the organization be picked when it is selectable', async () => {
    const { api } = await render({
      organization: { choices: [{ id: 'org-acme', name: 'Acme' }, { id: 'org-globex', name: 'Globex' }] },
      organizationRoute: true,
    });
    await mounted!.select(field('organization'), 'org-globex');
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledWith('org-globex', expect.anything());
  });

  it('says what the API refused', async () => {
    const api = fakeApi();
    api.createInOrganization.mockRejectedValueOnce(new Error('You cannot grant what you do not hold'));
    await render({ organizationRoute: true, api });
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(mounted!.host.querySelector('[role="alert"]')?.textContent).toBe('You cannot grant what you do not hold');
  });
});
