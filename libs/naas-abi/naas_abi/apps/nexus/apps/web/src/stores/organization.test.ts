import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.fn();

vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.example.test' }));
vi.mock('@/stores/auth', () => ({ authFetch: (...args: unknown[]) => authFetch(...args) }));
vi.mock('@/lib/org-branding', () => ({ invalidateOrgBranding: () => undefined }));

import { useOrganizationStore } from './organization';

const answer = (status: number, body: unknown) =>
  ({ ok: status < 400, status, json: () => Promise.resolve(body) }) as Response;

const sent = () => JSON.parse(authFetch.mock.calls.at(-1)?.[1]?.body as string);

describe('an invitation to an organization', () => {
  beforeEach(() => {
    authFetch.mockReset();
    authFetch.mockResolvedValue(answer(200, { id: 'm1', organization_id: 'acme', user_id: 'usr_bob', role: 'member' }));
  });

  it('carries the level, the org admin toggle, every workspace with "admin" and the groups, in one request', async () => {
    await useOrganizationStore.getState().inviteToOrganization('acme', {
      email: 'bob@example.com',
      level: 'member',
      orgAdmin: false,
      workspaces: [
        { id: 'ws-1', admin: true },
        { id: 'ws-2', admin: false },
      ],
      capabilities: ['grp_runners'],
      profile: { name: 'Bob', country: 'FR' },
    });
    expect(authFetch).toHaveBeenCalledTimes(1);
    expect(authFetch.mock.calls.at(-1)?.[0]).toBe('/api/organizations/acme/members/invite');
    expect(sent()).toEqual({
      email: 'bob@example.com',
      name: 'Bob',
      level: 'member',
      org_admin: false,
      workspaces: [
        { id: 'ws-1', admin: true },
        { id: 'ws-2', admin: false },
      ],
      capabilities: ['grp_runners'],
      country: 'FR',
    });
  });

  it('reads the created-or-linked answer: the org member, with its status', async () => {
    authFetch.mockResolvedValue(
      answer(200, {
        status: 'added',
        user: { id: 'usr_bob', email: 'bob@example.com', name: 'Bob', status: 'invited' },
        member: { id: 'm1', organization_id: 'acme', user_id: 'usr_bob', role: 'member', source: 'organization', status: 'invited' },
        provider: null,
        sign_in_email_sent: true,
        warning: null,
      })
    );
    const { member } = await useOrganizationStore.getState().inviteToOrganization('acme', {
      email: 'bob@example.com',
    });
    expect(member).toMatchObject({ userId: 'usr_bob', role: 'member', orgAdmin: false, source: 'organization', status: 'invited' });
  });

  it('has no member of the organization itself for someone joining workspaces only', async () => {
    authFetch.mockResolvedValue(
      answer(200, {
        status: 'added',
        user: { id: 'usr_bob', email: 'bob@example.com', name: 'Bob', status: 'invited' },
        member: null,
        provider: null,
        sign_in_email_sent: true,
        warning: null,
      })
    );
    const { member } = await useOrganizationStore.getState().inviteToOrganization('acme', {
      email: 'bob@example.com',
      workspaces: [{ id: 'ws-1', admin: false }],
    });
    expect(member).toBeNull();
    expect(sent()).toMatchObject({ org_admin: false, workspaces: [{ id: 'ws-1', admin: false }] });
  });

  it('names no role, no policy and no capability group when none is picked', async () => {
    await useOrganizationStore.getState().inviteToOrganization('acme', { email: 'bob@example.com', capabilities: [] });
    expect(sent()).not.toHaveProperty('role');
    expect(sent()).not.toHaveProperty('policy_ids');
    expect(sent()).not.toHaveProperty('capabilities');
  });

  it('says what IAM refused', async () => {
    authFetch.mockResolvedValue(answer(403, { detail: 'You cannot grant what you do not hold: nexus:UseFeature on graph' }));
    await expect(
      useOrganizationStore.getState().inviteToOrganization('acme', { email: 'bob@example.com', capabilities: ['grp_runners'] }),
    ).rejects.toThrow('You cannot grant what you do not hold');
  });
});

describe('the organization directory', () => {
  beforeEach(() => authFetch.mockReset());

  it('lists org admins, people of its workspaces only and invited people, with their level', async () => {
    authFetch.mockResolvedValue(
      answer(200, [
        { id: 'm1', organization_id: 'acme', user_id: 'usr_ann', role: 'admin', org_admin: true, level: 'member', source: 'organization', status: 'active' },
        { id: 'm2', organization_id: 'acme', user_id: 'usr_bob', role: null, level: 'viewer', source: 'workspace', status: 'invited' },
        // An older row: no source, status, level nor org_admin; an owner of before is an admin.
        { id: 'm3', organization_id: 'acme', user_id: 'usr_cat', role: 'member' },
        { id: 'm4', organization_id: 'acme', user_id: 'usr_dan', role: 'owner' },
      ])
    );
    const members = await useOrganizationStore.getState().fetchMembers('acme');
    expect(members.map((m) => [m.userId, m.role, m.orgAdmin, m.level, m.source, m.status])).toEqual([
      ['usr_ann', 'admin', true, 'member', 'organization', 'active'],
      ['usr_bob', null, false, 'viewer', 'workspace', 'invited'],
      ['usr_cat', 'member', false, null, 'organization', 'active'],
      ['usr_dan', 'admin', true, null, 'organization', 'active'],
    ]);
  });
});
