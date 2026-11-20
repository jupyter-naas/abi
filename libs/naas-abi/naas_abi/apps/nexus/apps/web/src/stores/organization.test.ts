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

  it('carries the picked policies as policy_ids, and every workspace in one request', async () => {
    await useOrganizationStore.getState().inviteToOrganization('acme', {
      email: 'bob@example.com',
      role: 'member',
      workspaces: [
        { id: 'ws-1', role: 'member' },
        { id: 'ws-2', role: 'viewer' },
      ],
      policyIds: ['pol_features', 'pol_graph'],
      profile: { name: 'Bob', country: 'FR' },
    });
    expect(authFetch).toHaveBeenCalledTimes(1);
    expect(authFetch.mock.calls.at(-1)?.[0]).toBe('/api/organizations/acme/members/invite');
    expect(sent()).toEqual({
      email: 'bob@example.com',
      name: 'Bob',
      role: 'member',
      workspaces: [
        { id: 'ws-1', role: 'member' },
        { id: 'ws-2', role: 'viewer' },
      ],
      policy_ids: ['pol_features', 'pol_graph'],
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
      role: 'member',
    });
    expect(member).toMatchObject({ userId: 'usr_bob', role: 'member', source: 'organization', status: 'invited' });
  });

  it('has no org member for workspace access only', async () => {
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
      role: null,
      workspaces: [{ id: 'ws-1', role: 'member' }],
    });
    expect(member).toBeNull();
    expect(sent()).toMatchObject({ role: null, workspaces: [{ id: 'ws-1', role: 'member' }] });
  });

  it('names no policy when none is picked', async () => {
    await useOrganizationStore.getState().inviteToOrganization('acme', { email: 'bob@example.com', role: 'member', policyIds: [] });
    expect(sent()).not.toHaveProperty('policy_ids');
  });

  it('says what IAM refused', async () => {
    authFetch.mockResolvedValue(answer(403, { detail: 'You cannot grant what you do not hold: nexus:UseFeature on graph' }));
    await expect(
      useOrganizationStore.getState().inviteToOrganization('acme', { email: 'bob@example.com', role: 'member', policyIds: ['pol_graph'] }),
    ).rejects.toThrow('You cannot grant what you do not hold');
  });
});

describe('the organization directory', () => {
  beforeEach(() => authFetch.mockReset());

  it('lists people with workspace access only (no role) and invited people', async () => {
    authFetch.mockResolvedValue(
      answer(200, [
        { id: 'm1', organization_id: 'acme', user_id: 'usr_ann', role: 'admin', source: 'organization', status: 'active' },
        { id: 'm2', organization_id: 'acme', user_id: 'usr_bob', role: null, source: 'workspace', status: 'invited' },
        // An older row: no source nor status.
        { id: 'm3', organization_id: 'acme', user_id: 'usr_cat', role: 'member' },
      ])
    );
    const members = await useOrganizationStore.getState().fetchMembers('acme');
    expect(members.map((m) => [m.userId, m.role, m.source, m.status])).toEqual([
      ['usr_ann', 'admin', 'organization', 'active'],
      ['usr_bob', null, 'workspace', 'invited'],
      ['usr_cat', 'member', 'organization', 'active'],
    ]);
  });
});
