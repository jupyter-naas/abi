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
import { readRoleOptions } from '@/lib/member-roles';

const ORG_ROLES = readRoleOptions({
  groups: [
    { kind: 'level', id: 'grp_m', name: 'Members', level: 'member' },
    { kind: 'level', id: 'grp_v', name: 'Viewers', level: 'viewer' },
    { kind: 'own', id: 'grp_people', name: 'Acme people' },
    { kind: 'admins', id: 'grp_oadmins', name: 'Acme admins' },
    { kind: 'group', id: 'grp_wa', name: 'Alpha workspace' },
    { kind: 'group', id: 'grp_wa_admins', name: 'Alpha admins' },
  ],
  policies: [{ kind: 'policy', id: 'pol_x', name: 'Acme reports' }],
});

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


async function render(props: Partial<CreateUserFormProps>) {
  const api = fakeApi();
  const onCreated = vi.fn();
  const set = vi.fn(async () => ({}));
  const options = vi.fn(async () => ORG_ROLES);
  mounted = await mount(CreateUserForm, {
    organization: { fixed: { id: 'org-acme', name: 'Acme' } },
    organizationRoute: false,
    subtitle: 'Create',
    back: { href: '/back', label: 'Back' },
    onCreated,
    onCancel: () => undefined,
    api,
    loadCapabilities: async () => [RUNNERS],
    rolesApi: { options, set },
    ...props,
  } as CreateUserFormProps);
  await mounted.flush();
  return { api, onCreated, set, options };
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
  it('asks for their Role, the organization\'s people and Members to start with, and makes it theirs', async () => {
    const { api, set } = await render({ organizationRoute: true });
    const tags = () => [...mounted!.host.querySelectorAll('[data-role]')].map((tag) => tag.textContent);
    expect(tags()).toEqual(['Acme people', 'Members']);
    expect(mounted!.host.querySelector('[data-workspace]')).toBeNull();
    expect(field('level')).toBeNull();
    await mounted!.select(field('add-role'), 'group:grp_wa_admins');
    await mounted!.select(field('add-role'), 'policy:pol_x');
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledWith(
      'org-acme',
      expect.objectContaining({ email: 'bob@example.com', level: 'member', orgAdmin: false, workspaces: [] })
    );
    expect(set).toHaveBeenCalledWith({ kind: 'organization', id: 'org-acme' }, 'usr_bob', {
      groups: ['grp_people', 'grp_m', 'grp_wa_admins'],
      policies: ['pol_x'],
    });
  });

  it('makes an org admin with the admins group', async () => {
    const { api } = await render({ organizationRoute: true });
    await mounted!.select(field('add-role'), 'admins:grp_oadmins');
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledWith('org-acme', expect.objectContaining({ orgAdmin: true }));
  });

  it('refuses a Role that gives nothing, before asking', async () => {
    const { api } = await render({ organizationRoute: true });
    await mounted!.click(mounted!.host.querySelector('[data-role="level"] button'));
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).not.toHaveBeenCalled();
    expect(mounted!.host.querySelector('[role="alert"]')?.textContent).toMatch(/use nothing/);
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
    const { api, options } = await render({
      organization: { choices: [{ id: 'org-acme', name: 'Acme' }, { id: 'org-globex', name: 'Globex' }] },
      organizationRoute: true,
    });
    await mounted!.select(field('organization'), 'org-globex');
    await mounted!.flush();
    expect(options).toHaveBeenLastCalledWith({ kind: 'organization', id: 'org-globex' });
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
