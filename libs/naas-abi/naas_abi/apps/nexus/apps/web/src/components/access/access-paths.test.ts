import { describe, expect, it } from 'vitest';
import {
  accessPathAt,
  oldAccessRedirect,
  organizationAccessPath,
  pageFocus,
  platformAccessPath,
  platformPersonPath,
  workspaceAccessPath,
  workspacePersonPath,
} from './access-paths';
import { organizationAccessScope, workspaceAccessScope } from './access-scope';

describe('the Access pages of each level', () => {
  it('gives every page and what it opens an address of its own', () => {
    expect(platformAccessPath('policies')).toBe('/settings/access/policies');
    expect(platformAccessPath('policies', 'builtin.owner')).toBe('/settings/access/policies/builtin.owner');
    expect(platformAccessPath('groups', 'grp/1')).toBe('/settings/access/groups/grp%2F1');
    expect(organizationAccessPath('org-1', 'groups', 'grp_1')).toBe('/organizations/org-1/settings/groups/grp_1');
    expect(workspaceAccessPath('ws-1', 'policies')).toBe('/workspace/ws-1/settings/policies');
    expect(platformPersonPath('usr_1')).toBe('/settings/users/usr_1');
    expect(workspacePersonPath('ws-1', 'usr_1')).toBe('/workspace/ws-1/settings/members/usr_1');
  });

  it('reads what an address has open, decoded, and nothing on the page itself', () => {
    const base = platformAccessPath('policies');
    expect(pageFocus(`${base}/pol%2F1?x=1`, base)).toBe('pol/1');
    expect(pageFocus(base, base)).toBeNull();
    expect(pageFocus('/settings/access/policiesx/a', base)).toBeNull();
  });

  it('finds the level of a container, none for another module or below one', () => {
    expect(accessPathAt('abi:', 'policies', 'p')).toBe('/settings/access/policies/p');
    expect(accessPathAt(null, 'groups')).toBe('/settings/access/groups');
    expect(accessPathAt(organizationAccessScope('org-1').value, 'policies')).toBe('/organizations/org-1/settings/policies');
    expect(accessPathAt(workspaceAccessScope('org-1', 'ws-1', 'W').value, 'policies', 'p')).toBe(
      '/workspace/ws-1/settings/policies/p'
    );
  });
});

describe('old Roles & permissions addresses', () => {
  it('send the platform’s sections to their page, People & roles to Users', () => {
    expect(oldAccessRedirect('/settings/roles')).toBe('/settings/access');
    expect(oldAccessRedirect('/settings/roles', '?section=policies')).toBe('/settings/access/policies');
    expect(oldAccessRedirect('/settings/roles', '?section=policies&policy=builtin.admin')).toBe(
      '/settings/access/policies/builtin.admin'
    );
    expect(oldAccessRedirect('/settings/roles', '?policy=pol_1')).toBe('/settings/access/policies/pol_1');
    expect(oldAccessRedirect('/settings/roles', '?section=groups&group=grp_1')).toBe('/settings/access/groups/grp_1');
    expect(oldAccessRedirect('/settings/roles', '?section=service-accounts')).toBe('/settings/access/service-accounts');
    expect(oldAccessRedirect('/settings/roles', '?section=approvals')).toBe('/settings/access/approvals');
    expect(oldAccessRedirect('/settings/roles', '?section=simulator')).toBe('/settings/access/simulator');
    expect(oldAccessRedirect('/settings/roles', '?section=audit')).toBe('/settings/access/audit');
    expect(oldAccessRedirect('/settings/roles', '?section=people')).toBe('/settings/users');
    expect(oldAccessRedirect('/settings/roles', '?section=people&person=usr_1')).toBe('/settings/users/usr_1');
    expect(oldAccessRedirect('/settings/roles', '?person=usr_1')).toBe('/settings/users/usr_1');
  });

  it('keep the rest of the query', () => {
    expect(oldAccessRedirect('/settings/roles', '?section=policies&x=1')).toBe('/settings/access/policies?x=1');
    expect(oldAccessRedirect('/settings/roles/', '?section=unknown')).toBe('/settings/access');
  });

  it('send an organization’s to its Policies or Groups, People & roles to its Members', () => {
    const roles = '/organizations/org-1/settings/roles';
    expect(oldAccessRedirect(roles)).toBe('/organizations/org-1/settings/policies');
    expect(oldAccessRedirect(roles, '?section=policies&policy=pol_1')).toBe('/organizations/org-1/settings/policies/pol_1');
    expect(oldAccessRedirect(roles, '?section=groups&group=grp_1')).toBe('/organizations/org-1/settings/groups/grp_1');
    expect(oldAccessRedirect(roles, '?section=people')).toBe('/organizations/org-1/settings/users');
    expect(oldAccessRedirect(roles, '?section=people&person=usr_1')).toBe('/organizations/org-1/settings/users/usr_1');
    // The platform-only sections were never an organization's: its first page.
    expect(oldAccessRedirect(roles, '?section=audit')).toBe('/organizations/org-1/settings/policies');
  });

  it('send a workspace’s to its Policies or Groups, People & roles to its Members, behind an org prefix too', () => {
    const permissions = '/workspace/ws-1/settings/permissions';
    expect(oldAccessRedirect(permissions)).toBe('/workspace/ws-1/settings/policies');
    expect(oldAccessRedirect(permissions, '?section=policies&policy=pol_1')).toBe('/workspace/ws-1/settings/policies/pol_1');
    expect(oldAccessRedirect(permissions, '?section=groups')).toBe('/workspace/ws-1/settings/groups');
    expect(oldAccessRedirect(permissions, '?section=people&person=usr_1')).toBe('/workspace/ws-1/settings/members/usr_1');
    expect(oldAccessRedirect('/org/acme/workspace/ws-1/settings/permissions', '?section=groups&group=g')).toBe(
      '/org/acme/workspace/ws-1/settings/groups/g'
    );
  });

  it('leave every other address alone', () => {
    for (const path of [
      '/settings/access/policies',
      '/settings/users/usr_1',
      '/organizations/org-1/settings/policies',
      '/workspace/ws-1/settings/policies',
      '/workspace/ws-1/settings/members',
      '/settings/rolesx',
    ]) {
      expect(oldAccessRedirect(path, '?section=people')).toBeNull();
    }
  });
});
