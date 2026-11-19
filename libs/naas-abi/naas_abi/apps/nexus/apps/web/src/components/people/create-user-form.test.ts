// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';
import type { CreatedPerson, PeopleApi } from '@/lib/people';

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

const WORKSPACES = [
  { id: 'ws-b', name: 'Beta' },
  { id: 'ws-a', name: 'Alpha' },
];

async function render(props: Partial<CreateUserFormProps>) {
  const api = fakeApi();
  const onCreated = vi.fn();
  mounted = await mount(CreateUserForm, {
    organization: { fixed: { id: 'org-acme', name: 'Acme' } },
    orgRoles: [],
    workspaceRoles: ['member', 'viewer', 'admin'],
    subtitle: 'Create',
    back: { href: '/back', label: 'Back' },
    onCreated,
    onCancel: () => undefined,
    api,
    loadWorkspaces: async () => WORKSPACES,
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
  it('shows the organization read-only, asks no org role, and is prefilled', async () => {
    await render({ attachedWorkspace: { id: 'ws-research', name: 'Research' }, prefill: { email: 'zoe@other.org' } });
    const org = field<HTMLInputElement>('organization')!;
    expect(org.value).toBe('Acme');
    expect(org.readOnly).toBe(true);
    expect(field('org-role')).toBeNull();
    expect(mounted!.host.querySelector<HTMLInputElement>('#create-user-email')!.value).toBe('zoe@other.org');
    expect(mounted!.host.querySelector('label[for="create-user-workspace-role"]')?.textContent).toBe('Role in Research');
    // No organization workspaces to pick, and no org picture: the person gets no org role.
    expect(mounted!.host.querySelector('[data-workspace]')).toBeNull();
    expect(mounted!.host.querySelector('.account-profile-avatar-section')).toBeNull();
  });

  it('creates them into the workspace, in one request', async () => {
    const { api, onCreated } = await render({
      attachedWorkspace: { id: 'ws-research', name: 'Research' },
      prefill: { name: 'Zoé' },
    });
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'zoe@other.org');
    await mounted!.select(field('workspace-role'), 'viewer');
    await create();
    expect(api.createInWorkspace).toHaveBeenCalledTimes(1);
    expect(api.createInWorkspace).toHaveBeenCalledWith('ws-research', {
      email: 'zoe@other.org',
      name: 'Zoé',
      role: 'viewer',
      policyIds: [],
      provider: undefined,
      profile: undefined,
    });
    expect(api.createInOrganization).not.toHaveBeenCalled();
    expect(onCreated).toHaveBeenCalledWith(CREATED, expect.objectContaining({ route: 'workspace' }));
  });
});

describe('Create user, from the organization', () => {
  it('offers None (workspace access only) once a workspace is picked, and sends every workspace at once', async () => {
    const { api } = await render({ orgRoles: ['member', 'admin'] });
    const roles = () => [...field<HTMLSelectElement>('org-role')!.options].map((o) => o.value);
    expect(roles()).toEqual(['member', 'admin']);
    expect([...mounted!.host.querySelectorAll('[data-workspace]')].map((li) => li.getAttribute('data-workspace'))).toEqual([
      'ws-a',
      'ws-b',
    ]);
    await mounted!.click(mounted!.host.querySelector('[data-workspace="ws-a"] input[type="checkbox"]'));
    await mounted!.click(mounted!.host.querySelector('[data-workspace="ws-b"] input[type="checkbox"]'));
    await mounted!.select(mounted!.host.querySelector('[data-workspace="ws-b"] select'), 'viewer');
    expect(roles()).toEqual(['member', 'admin', 'none']);
    await mounted!.select(field('org-role'), 'none');
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledTimes(1);
    expect(api.createInOrganization).toHaveBeenCalledWith(
      'org-acme',
      expect.objectContaining({
        email: 'bob@example.com',
        role: null,
        workspaces: [
          { id: 'ws-a', role: 'member' },
          { id: 'ws-b', role: 'viewer' },
        ],
      })
    );
  });

  it('shows the message the page returns, and empties the form', async () => {
    const { api } = await render({ orgRoles: ['member', 'admin'], onCreated: () => 'bob@example.com was added to Acme.' });
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledWith('org-acme', expect.objectContaining({ role: 'member', workspaces: [] }));
    expect(mounted!.host.querySelector('[role="status"]')?.textContent).toBe('bob@example.com was added to Acme.');
    expect(mounted!.host.querySelector<HTMLInputElement>('#create-user-email')!.value).toBe('');
  });

  it('lets the organization be picked when it is selectable', async () => {
    const { api } = await render({
      organization: { choices: [{ id: 'org-acme', name: 'Acme' }, { id: 'org-globex', name: 'Globex' }] },
      orgRoles: ['member'],
    });
    await mounted!.select(field('organization'), 'org-globex');
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(api.createInOrganization).toHaveBeenCalledWith('org-globex', expect.anything());
  });

  it('says what the API refused', async () => {
    const api = fakeApi();
    api.createInOrganization.mockRejectedValueOnce(new Error('You cannot grant what you do not hold'));
    await render({ orgRoles: ['member'], api });
    await mounted!.type(mounted!.host.querySelector('#create-user-email'), 'bob@example.com');
    await create();
    expect(mounted!.host.querySelector('[role="alert"]')?.textContent).toBe('You cannot grant what you do not hold');
  });
});
