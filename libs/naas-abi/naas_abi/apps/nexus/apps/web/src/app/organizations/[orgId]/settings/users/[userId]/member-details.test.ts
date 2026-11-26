import { describe, expect, it, vi } from 'vitest';
import { changedProfileFields, saveMemberChanges, type MemberOrganizationProfile } from './member-details';

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
