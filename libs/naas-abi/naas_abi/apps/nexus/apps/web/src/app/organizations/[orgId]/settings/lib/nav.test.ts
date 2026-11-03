import { describe, expect, it } from 'vitest';

import { isOrgAdminRole, orgSectionRedirect, orgSettingsAccess, orgSettingsNavForRole } from './nav';
import { orgSettingsRedirect } from './redirects';

describe('org settings nav', () => {
  it('gives a member no section, and one holding iam: rights there Roles & permissions alone', () => {
    expect(isOrgAdminRole('member')).toBe(false);
    expect(orgSettingsNavForRole('member')).toEqual([]);
    expect(orgSettingsNavForRole(null)).toEqual([]);
    expect(orgSettingsNavForRole('member', { holdsIam: true }).map((item) => item.slug)).toEqual(['roles']);
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

describe('orgSettingsAccess', () => {
  it('opens to owners and admins at once, by their role', () => {
    for (const role of ['owner', 'admin']) {
      expect(orgSettingsAccess({ role, roleKnown: true, holdsIam: false, accessSettled: false })).toBe('admin');
    }
  });
  it('waits for the role and the access before deciding for anyone else', () => {
    expect(orgSettingsAccess({ role: null, roleKnown: false, holdsIam: false, accessSettled: true })).toBe('unknown');
    expect(orgSettingsAccess({ role: 'member', roleKnown: true, holdsIam: false, accessSettled: false })).toBe('unknown');
  });
  it('gives Roles & permissions to an iam: holder, nothing to a member (Eve)', () => {
    expect(orgSettingsAccess({ role: 'member', roleKnown: true, holdsIam: true, accessSettled: true })).toBe('iam');
    expect(orgSettingsAccess({ role: 'member', roleKnown: true, holdsIam: false, accessSettled: true })).toBe('none');
    expect(orgSettingsAccess({ role: null, roleKnown: true, holdsIam: false, accessSettled: true })).toBe('none');
  });
});

describe('orgSectionRedirect', () => {
  it('waits for the access read before deciding for a non-admin', () => {
    expect(orgSectionRedirect({ section: 'general', role: 'member', roleKnown: true, holdsIam: false, accessSettled: false })).toBeNull();
    expect(orgSectionRedirect({ section: 'roles', role: 'member', roleKnown: true, holdsIam: false, accessSettled: false })).toBeNull();
  });
  it('sends an iam: holder to Roles & permissions, and lets anyone else stay (the layout refuses)', () => {
    expect(orgSectionRedirect({ section: 'general', role: 'member', roleKnown: true, holdsIam: true, accessSettled: true })).toBe('roles');
    expect(orgSectionRedirect({ section: 'users', role: 'member', roleKnown: true, holdsIam: true, accessSettled: true })).toBe('roles');
    expect(orgSectionRedirect({ section: 'roles', role: 'member', roleKnown: true, holdsIam: true, accessSettled: true })).toBeNull();
    expect(orgSectionRedirect({ section: 'general', role: 'member', roleKnown: true, holdsIam: false, accessSettled: true })).toBeNull();
  });
  it('never moves owners and admins, and nothing before the role is known', () => {
    expect(orgSectionRedirect({ section: 'users', role: 'admin', roleKnown: true, holdsIam: false, accessSettled: false })).toBeNull();
    expect(orgSectionRedirect({ section: 'roles', role: null, roleKnown: true, holdsIam: true, accessSettled: true })).toBeNull();
    // No role there, IAM rights (a platform admin who is no member): sent to Roles & permissions.
    expect(orgSectionRedirect({ section: 'users', role: null, roleKnown: true, holdsIam: true, accessSettled: true })).toBe('roles');
    expect(orgSectionRedirect({ section: 'branding', role: null, roleKnown: true, holdsIam: true, accessSettled: true })).toBe('roles');
    // Nothing is decided before the role is read.
    expect(orgSectionRedirect({ section: 'users', role: null, roleKnown: false, holdsIam: true, accessSettled: true })).toBeNull();
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
