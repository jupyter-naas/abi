import { describe, expect, it, vi } from 'vitest';
import { changedProfileFields, saveMemberChanges, type MemberOrganizationProfile } from './member-details';
import { accessChanges, accessError, initialAccess, type AccessDraft, type MemberDetails } from './member-details';

const saved: MemberOrganizationProfile = {
  organization: null,
  job_title: null,
  service_line: null,
  country: 'France',
  interest: null,
  bio: 'Org bio',
  avatar: null,
};

const blank = { service_line: '', country: 'France', interest: '' };

describe('changedProfileFields', () => {
  it('sends nothing when nothing changed, even for unset fields left empty', () => {
    expect(
      changedProfileFields(saved, {
        ...blank,
        organization: '',
        job_title: '',
        bio: 'Org bio',
      })
    ).toEqual({});
  });

  it('sends only the edited fields, trimmed', () => {
    expect(
      changedProfileFields(saved, {
        ...blank,
        organization: '  Acme ',
        job_title: '',
        service_line: 'Audit',
        bio: '',
      })
    ).toEqual({ organization: 'Acme', service_line: 'Audit', bio: '' });
  });
});

describe('saveMemberChanges', () => {
  it('saves the profile then the access, and refreshes the members after an access change', async () => {
    const calls: string[] = [];
    const failed = await saveMemberChanges({
      profile: async () => void calls.push('profile'),
      access: async () => void calls.push('access'),
      refreshed: async () => void calls.push('refreshed'),
    });
    expect(failed).toBeNull();
    expect(calls).toEqual(['profile', 'access', 'refreshed']);
  });

  it('says the profile was saved when only the access is refused', async () => {
    const refreshed = vi.fn();
    const failed = await saveMemberChanges({
      profile: async () => undefined,
      access: () => Promise.reject(new Error('An organization keeps at least one admin')),
      refreshed,
    });
    expect(failed).toBe('The profile was saved, but their access was not changed: An organization keeps at least one admin');
    expect(refreshed).not.toHaveBeenCalled();
  });

  it('changes no access when the profile is refused', async () => {
    const access = vi.fn();
    const failed = await saveMemberChanges({ profile: () => Promise.reject(new Error('Too long')), access, refreshed: vi.fn() });
    expect(failed).toBe('The profile was not saved: Too long');
    expect(access).not.toHaveBeenCalled();
  });
});

const details = (over: Partial<MemberDetails['member']> = {}, extra: Partial<MemberDetails> = {}): MemberDetails => ({
  member: {
    id: 'm',
    organization_id: 'acme',
    user_id: 'usr_bob',
    role: 'member',
    org_admin: false,
    level: 'member',
    email: 'bob@example.com',
    name: 'Bob',
    created_at: null,
    ...over,
  },
  account: {} as MemberDetails['account'],
  organization_profile: saved,
  workspaces: [
    { id: 'ws-1', name: 'Alpha', slug: 'alpha', role: 'admin', source: 'workspace', admin: true },
    { id: 'ws-2', name: 'Beta', slug: 'beta', role: 'member', source: 'workspace', admin: false },
    // Reached through an org admin role: not one they joined.
    { id: 'ws-3', name: 'Gamma', slug: 'gamma', role: 'admin', source: 'organization' },
  ],
  capabilities: [{ id: 'grp_runners', name: 'Workflow runners', owner_scope: 'abi:nexus:organization/acme' }],
  ...extra,
});

describe('the access of a member', () => {
  it('starts at their org admin toggle, level, workspaces joined with "admin", and groups', () => {
    expect(initialAccess(details())).toEqual({
      orgAdmin: false,
      level: 'member',
      workspaces: [
        { id: 'ws-1', admin: true },
        { id: 'ws-2', admin: false },
      ],
      capabilities: ['grp_runners'],
    });
    // An older answer: the org role says it, an owner of before is an admin.
    expect(initialAccess(details({ role: 'admin', org_admin: undefined, level: undefined }, { capabilities: undefined }))).toMatchObject({
      orgAdmin: true,
      level: null,
      capabilities: [],
    });
  });

  it('sends only what changed: the member change, the workspaces, or both', () => {
    const saved: AccessDraft = initialAccess(details());
    expect(accessChanges(saved, saved)).toEqual({ member: null, workspaces: null });
    expect(accessChanges(saved, { ...saved, level: 'viewer', workspaces: [{ id: 'ws-2', admin: false }] })).toEqual({
      member: { level: 'viewer' },
      workspaces: [{ id: 'ws-2', admin: false }],
    });
    expect(accessChanges(saved, { ...saved, orgAdmin: true, capabilities: [] })).toEqual({
      member: { orgAdmin: true, capabilities: [] },
      workspaces: null,
    });
    // The order of the workspaces picked is no change.
    expect(
      accessChanges(saved, { ...saved, workspaces: [{ id: 'ws-2', admin: false }, { id: 'ws-1', admin: true }] }).workspaces
    ).toBeNull();
  });

  it('refuses a Viewer who administers a workspace', () => {
    const saved = initialAccess(details());
    expect(accessError({ ...saved, level: 'viewer' })).toMatch(/workspace admin is a Member/);
    expect(accessError(saved)).toBeNull();
  });
});
