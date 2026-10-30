import { describe, expect, it } from 'vitest';

import { isOrgAdminRole, orgSectionRedirect, orgSettingsNavForRole } from './nav';
import { orgSettingsRedirect } from './redirects';

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
      'users',
      'roles',
    ]);
    expect(orgSettingsNavForRole('admin').map((item) => item.slug)).not.toContain(
      'secrets'
    );
  });
});

describe('orgSectionRedirect', () => {
  it('waits for the access read before sending a member off Roles & permissions', () => {
    // The org was read first (role known), /access is still in flight.
    expect(orgSectionRedirect({ section: 'roles', role: 'member', holdsIam: false, accessSettled: false })).toBeNull();
    // It answers: a delegated IAM admin stays, anyone else goes to General.
    expect(orgSectionRedirect({ section: 'roles', role: 'member', holdsIam: true, accessSettled: true })).toBeNull();
    expect(orgSectionRedirect({ section: 'roles', role: 'member', holdsIam: false, accessSettled: true })).toBe('general');
  });

  it('decides admin-only sections by role alone, and nothing before the role is known', () => {
    expect(orgSectionRedirect({ section: 'users', role: 'member', holdsIam: false, accessSettled: false })).toBe('general');
    expect(orgSectionRedirect({ section: 'users', role: 'admin', holdsIam: false, accessSettled: false })).toBeNull();
    expect(orgSectionRedirect({ section: 'roles', role: null, holdsIam: false, accessSettled: true })).toBeNull();
    expect(orgSectionRedirect({ section: 'general', role: 'member', holdsIam: false, accessSettled: true })).toBeNull();
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
  });

  it('sends Modules & features, removed with the sets, to Roles & permissions', () => {
    expect(orgSettingsRedirect('/organizations/org-1/settings/modules')).toBe('/organizations/org-1/settings/roles');
    expect(orgSettingsRedirect('/organizations/org-1/settings/modules', '?workspace=ws-1')).toBe(
      '/organizations/org-1/settings/roles?workspace=ws-1'
    );
    expect(orgSettingsRedirect('/organizations/org-1/settings/constructor')).toBeNull();
  });
});
