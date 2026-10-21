import { describe, expect, it } from 'vitest';
import { changedProfileFields, type MemberOrganizationProfile } from './member-details';

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
