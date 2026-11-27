import { describe, expect, it } from 'vitest';

import { isOrgAdminRole, orgSectionRedirect, orgSettingsAccess, orgSettingsNavForRole } from './nav';
import { orgSettingsRedirect } from './redirects';

const iam = (...actions: string[]) => ({ actions: Object.fromEntries(actions.map((a) => [a, true])) });
const POLICIES = iam('iam:ListPolicies');
const BOTH = iam('iam:ListPolicies', 'iam:ListGroups');
const slugs = (role: string | null, access?: ReturnType<typeof iam> | null) =>
  orgSettingsNavForRole(role, { access }).map((item) => item.slug);

describe('org settings nav', () => {
  it('gives a member no section, and one holding iam: rights there the Access pages IAM opens', () => {
    expect(isOrgAdminRole('member')).toBe(false);
    expect(orgSettingsNavForRole('member')).toEqual([]);
    expect(orgSettingsNavForRole(null)).toEqual([]);
    expect(slugs('member', POLICIES)).toEqual(['policies']);
    expect(slugs('member', BOTH)).toEqual(['groups', 'policies']);
    // Whoever may list who holds what sees the policies held here.
    expect(slugs('member', iam('iam:ListAttachments'))).toEqual(['policies']);
    expect(slugs('member', iam('iam:Explain', 'nexus:ReadSystem'))).toEqual([]);
  });

  it('shows users to owners', () => {
    expect(slugs('owner')).toContain('users');
  });

  it('shows Access › Policies and Groups to whoever IAM lets open each there, whatever their role', () => {
    for (const role of ['owner', 'admin', 'member', null]) {
      expect(slugs(role)).not.toContain('policies');
      expect(slugs(role, iam('iam:ListGroups'))).toEqual(expect.arrayContaining(['groups']));
      expect(slugs(role, iam('iam:ListGroups'))).not.toContain('policies');
      expect(slugs(role, BOTH)).toEqual(expect.arrayContaining(['policies', 'groups']));
    }
    expect(slugs('owner', BOTH)).not.toContain('roles');
    expect(slugs('owner', BOTH)).not.toContain('access');
    const access = orgSettingsNavForRole('owner', { access: BOTH }).filter((item) => item.group === 'Access');
    // Its offer's pages follow, for its owners and admins.
    expect(access.map((item) => item.label)).toEqual(['Features', 'Services', 'Modules', 'Policies']);
  });

  it('shows branding to admins and hides domains, servers, services, and billing', () => {
    expect(slugs('owner', BOTH)).toEqual([
      'general',
      'branding',
      'workspaces',
      'users',
      'groups',
      'features',
      'core-services',
      'modules',
      'policies',
    ]);
    expect(slugs('admin')).not.toContain('secrets');
  });
});

describe('org settings nav › Analytics', () => {
  it('keeps Analytics and Access listed for an owner while their reads have not answered', () => {
    const pending = orgSettingsNavForRole('owner', { accessKnown: false, analyticsKnown: false }).map((item) => item.slug);
    expect(pending).toEqual(expect.arrayContaining(['analytics', 'groups', 'policies']));
    const denied = orgSettingsNavForRole('admin', {
      access: iam(),
      readsAnalytics: false,
      accessKnown: true,
      analyticsKnown: true,
    }).map((item) => item.slug);
    expect(denied).not.toContain('analytics');
    expect(denied).not.toContain('groups');
    expect(denied).not.toContain('policies');
  });

  it('shows Analytics to an owner or admin once the API says they may read it', () => {
    for (const role of ['owner', 'admin']) {
      expect(orgSettingsNavForRole(role).map((item) => item.slug)).not.toContain('analytics');
      expect(orgSettingsNavForRole(role, { readsAnalytics: true }).map((item) => item.slug)).toContain('analytics');
    }
  });

  it('shows no Analytics to a member or someone with no role, whatever the API says', () => {
    for (const role of ['member', null]) {
      expect(orgSettingsNavForRole(role, { readsAnalytics: true }).map((item) => item.slug)).not.toContain('analytics');
      expect(orgSettingsNavForRole(role, { access: BOTH, readsAnalytics: true }).map((item) => item.slug)).toEqual([
        'groups',
        'policies',
      ]);
    }
  });

  it('lists Analytics after Users and Groups, before the Access pages', () => {
    expect(
      orgSettingsNavForRole('owner', { access: BOTH, readsAnalytics: true }).map((item) => item.slug)
    ).toEqual([
      'general',
      'branding',
      'workspaces',
      'users',
      'groups',
      'analytics',
      'features',
      'core-services',
      'modules',
      'policies',
    ]);
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
  it('gives Access to an iam: holder, nothing to a member (Eve)', () => {
    expect(orgSettingsAccess({ role: 'member', roleKnown: true, holdsIam: true, accessSettled: true })).toBe('iam');
    expect(orgSettingsAccess({ role: 'member', roleKnown: true, holdsIam: false, accessSettled: true })).toBe('none');
    expect(orgSettingsAccess({ role: null, roleKnown: true, holdsIam: false, accessSettled: true })).toBe('none');
  });
});

describe('orgSectionRedirect', () => {
  const at = (section: string, role: string | null, access: ReturnType<typeof iam> | null, over = {}) =>
    orgSectionRedirect({ section, role, roleKnown: true, access, accessSettled: true, ...over });
  it('waits for the access read before deciding for a non-admin', () => {
    expect(at('general', 'member', null, { accessSettled: false })).toBeNull();
    expect(at('policies', 'member', null, { accessSettled: false })).toBeNull();
  });
  it('sends an iam: holder to the first Access page they hold, and lets anyone else stay (the layout refuses)', () => {
    expect(at('general', 'member', POLICIES)).toBe('policies');
    expect(at('users', 'member', BOTH)).toBe('groups');
    expect(at('general', 'member', iam('iam:ListGroups'))).toBe('groups');
    expect(at('policies', 'member', POLICIES)).toBeNull();
    expect(at('groups', 'member', BOTH)).toBeNull();
    // A page of Access IAM does not open to them: the first one it does.
    expect(at('groups', 'member', POLICIES)).toBe('policies');
    expect(at('general', 'member', iam())).toBeNull();
  });
  it('lets an iam: holder open a member’s page from a policy’s holders', () => {
    expect(at('users', 'member', POLICIES, { memberPage: true })).toBeNull();
    expect(at('users', 'member', POLICIES, { memberPage: false })).toBe('policies');
  });
  it('never moves owners and admins, and nothing before the role is known', () => {
    expect(at('users', 'admin', null, { accessSettled: false })).toBeNull();
    expect(at('branding', 'owner', iam())).toBeNull();
    expect(at('policies', null, POLICIES)).toBeNull();
    // No role there, IAM rights (a platform admin who is no member): sent to Access.
    expect(at('users', null, POLICIES)).toBe('policies');
    expect(at('branding', null, BOTH)).toBe('groups');
    // Nothing is decided before the role is read.
    expect(at('users', null, POLICIES, { roleKnown: false })).toBeNull();
  });
});

describe('orgSettingsRedirect', () => {
  it('sends the old Access section to Access › Policies, with its query', () => {
    expect(orgSettingsRedirect('/organizations/org-1/settings/access')).toBe('/organizations/org-1/settings/policies');
    expect(orgSettingsRedirect('/organizations/org-1/settings/access/x', '?a=1')).toBe(
      '/organizations/org-1/settings/policies?a=1'
    );
    expect(orgSettingsRedirect('/organizations/org-1/settings/policies')).toBeNull();
    expect(orgSettingsRedirect('/organizations/org-1/settings/users')).toBeNull();
  });

  it('leaves Modules, a page again (Access › Modules), where it is', () => {
    expect(orgSettingsRedirect('/organizations/org-1/settings/modules')).toBeNull();
    expect(orgSettingsRedirect('/organizations/org-1/settings/constructor')).toBeNull();
  });
});
