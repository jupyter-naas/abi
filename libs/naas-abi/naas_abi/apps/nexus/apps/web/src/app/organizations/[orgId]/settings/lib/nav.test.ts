import { describe, expect, it } from 'vitest';

import { isOrgAdminRole, orgModulesPath, orgSettingsNavForRole } from './nav';

describe('org settings nav', () => {
  it('hides admin sections from members', () => {
    expect(isOrgAdminRole('member')).toBe(false);
    expect(orgSettingsNavForRole('member').map((item) => item.slug)).toEqual([
      'general',
      'workspaces',
      'modules',
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
      'modules',
      'users',
      'roles',
      'access',
    ]);
    expect(orgSettingsNavForRole('admin').map((item) => item.slug)).not.toContain(
      'secrets'
    );
  });
});

describe('orgModulesPath', () => {
  it('opens Modules & features, at a workspace when given', () => {
    expect(orgModulesPath('org-1')).toBe('/organizations/org-1/settings/modules');
    expect(orgModulesPath('org-1', 'ws 1')).toBe('/organizations/org-1/settings/modules?workspace=ws%201');
  });
});
