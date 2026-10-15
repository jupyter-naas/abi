import { describe, expect, it } from 'vitest';

import { isOrgAdminRole, orgSettingsNavForRole } from './nav';

describe('org settings nav', () => {
  it('hides admin sections from members', () => {
    expect(isOrgAdminRole('member')).toBe(false);
    expect(orgSettingsNavForRole('member').map((item) => item.slug)).toEqual([
      'general',
      'workspaces',
    ]);
  });

  it('shows users to owners', () => {
    expect(orgSettingsNavForRole('owner').map((item) => item.slug)).toContain(
      'users'
    );
  });

  it('hides branding, domains, servers, services, and billing from the sidebar', () => {
    expect(orgSettingsNavForRole('owner').map((item) => item.slug)).toEqual([
      'general',
      'workspaces',
      'users',
      'roles',
    ]);
    expect(orgSettingsNavForRole('admin').map((item) => item.slug)).not.toContain(
      'secrets'
    );
  });
});
