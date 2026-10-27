import { describe, expect, it } from 'vitest';

import { isOrgAdminRole, orgModulesPath, orgSettingsNavForRole } from './nav';
import { orgSettingsRedirect } from './redirects';

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

  it('shows Roles & permissions to whoever holds an iam: action there, whatever their role', () => {
    for (const role of ['owner', 'admin', 'member', null]) {
      expect(orgSettingsNavForRole(role).map((item) => item.slug)).not.toContain('roles');
      expect(orgSettingsNavForRole(role, { holdsIam: true }).map((item) => item.slug)).toContain('roles');
    }
    expect(orgSettingsNavForRole('owner', { holdsIam: true }).map((item) => item.slug)).not.toContain('access');
  });

  it('shows branding to admins and hides domains, servers, services, and billing', () => {
    expect(orgSettingsNavForRole('owner', { holdsIam: true }).map((item) => item.slug)).toEqual([
      'general',
      'branding',
      'workspaces',
      'modules',
      'users',
      'roles',
    ]);
    expect(orgSettingsNavForRole('admin').map((item) => item.slug)).not.toContain(
      'secrets'
    );
  });
});

describe('orgSettingsRedirect', () => {
  it('sends the old Access section to Roles & permissions, with its query', () => {
    expect(orgSettingsRedirect('/organizations/org-1/settings/access')).toBe('/organizations/org-1/settings/roles');
    expect(orgSettingsRedirect('/organizations/org-1/settings/access/x', '?a=1')).toBe(
      '/organizations/org-1/settings/roles?a=1'
    );
    expect(orgSettingsRedirect('/organizations/org-1/settings/roles')).toBeNull();
    expect(orgSettingsRedirect('/organizations/org-1/settings/users')).toBeNull();
    expect(orgSettingsRedirect('/organizations/org-1/settings/constructor')).toBeNull();
  });
});

describe('orgModulesPath', () => {
  it('opens Modules & features, at a workspace when given', () => {
    expect(orgModulesPath('org-1')).toBe('/organizations/org-1/settings/modules');
    expect(orgModulesPath('org-1', 'ws 1')).toBe('/organizations/org-1/settings/modules?workspace=ws%201');
  });
});
