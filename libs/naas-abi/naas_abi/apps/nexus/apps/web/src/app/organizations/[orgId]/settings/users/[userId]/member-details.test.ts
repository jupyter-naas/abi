import { describe, expect, it, vi } from 'vitest';
import { changedProfileFields, type MemberOrganizationProfile } from './member-details';
import { saveMemberChanges } from './member-details';

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
  it('saves the profile then the role, and refreshes the members after a role change', async () => {
    const calls: string[] = [];
    const failed = await saveMemberChanges({
      profile: async () => void calls.push('profile'),
      role: async () => void calls.push('role'),
      refreshed: async () => void calls.push('refreshed'),
    });
    expect(failed).toBeNull();
    expect(calls).toEqual(['profile', 'role', 'refreshed']);
  });

  it('says the profile was saved when only the role is refused', async () => {
    const refreshed = vi.fn();
    const failed = await saveMemberChanges({
      profile: async () => undefined,
      role: () => Promise.reject(new Error('An admin cannot demote an owner')),
      refreshed,
    });
    expect(failed).toBe('The profile was saved, but the role was not changed: An admin cannot demote an owner');
    expect(refreshed).not.toHaveBeenCalled();
  });

  it('changes no role when the profile is refused', async () => {
    const role = vi.fn();
    const failed = await saveMemberChanges({ profile: () => Promise.reject(new Error('Too long')), role, refreshed: vi.fn() });
    expect(failed).toBe('The profile was not saved: Too long');
    expect(role).not.toHaveBeenCalled();
  });
});
