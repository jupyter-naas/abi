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

  it('shows access to admins and owners only', () => {
    for (const role of ['admin', 'owner']) {
      expect(orgSettingsNavForRole(role).map((item) => item.slug)).toContain('access');
    }
    expect(orgSettingsNavForRole('member').map((item) => item.slug)).not.toContain('access');
  });

  it('shows branding to admins and hides domains, servers, services, and billing', () => {
    expect(orgSettingsNavForRole('owner').map((item) => item.slug)).toEqual([
      'general',
      'branding',
      'workspaces',
      'users',
      'roles',
      'access',
    ]);
    expect(orgSettingsNavForRole('admin').map((item) => item.slug)).not.toContain(
      'secrets'
    );
  });
});
