import { describe, expect, it } from 'vitest';

import { parseOrgSettingsRoute } from './org-settings-route';

describe('parseOrgSettingsRoute', () => {
  it('shows the settings list on the bare settings route', () => {
    expect(parseOrgSettingsRoute('/organizations/org-1/settings')).toEqual({
      isOrgSettingsRoute: true,
      orgId: 'org-1',
      isDetail: false,
      section: null,
      sectionLabel: null,
    });
  });

  it('opens a detail section for a settings slug', () => {
    expect(parseOrgSettingsRoute('/organizations/org-1/settings/branding')).toEqual({
      isOrgSettingsRoute: true,
      orgId: 'org-1',
      isDetail: true,
      section: 'branding',
      sectionLabel: 'Branding',
    });
  });

  it('labels the general section', () => {
    expect(parseOrgSettingsRoute('/organizations/abc/settings/general')).toEqual({
      isOrgSettingsRoute: true,
      orgId: 'abc',
      isDetail: true,
      section: 'general',
      sectionLabel: 'General',
    });
  });

  it('labels the users section (not admins)', () => {
    expect(parseOrgSettingsRoute('/organizations/org-1/settings/users')).toEqual({
      isOrgSettingsRoute: true,
      orgId: 'org-1',
      isDetail: true,
      section: 'users',
      sectionLabel: 'Users',
    });
  });

  it('labels the roles section', () => {
    expect(parseOrgSettingsRoute('/organizations/org-1/settings/roles')).toEqual({
      isOrgSettingsRoute: true,
      orgId: 'org-1',
      isDetail: true,
      section: 'roles',
      sectionLabel: 'Roles',
    });
  });

  it('ignores a trailing slash on the index', () => {
    expect(parseOrgSettingsRoute('/organizations/org-1/settings/')).toEqual({
      isOrgSettingsRoute: true,
      orgId: 'org-1',
      isDetail: false,
      section: null,
      sectionLabel: null,
    });
  });

  it('stops at a query string or fragment', () => {
    expect(parseOrgSettingsRoute('/organizations/org-1/settings/billing?tab=plans').section).toBe(
      'billing'
    );
    expect(
      parseOrgSettingsRoute('/organizations/org-1/settings/workspaces#list').sectionLabel
    ).toBe('Workspaces');
  });

  it('does not claim the organizations picker or tenant portal', () => {
    expect(parseOrgSettingsRoute('/organizations').isOrgSettingsRoute).toBe(false);
    expect(parseOrgSettingsRoute('/org/acme/auth/login').isOrgSettingsRoute).toBe(false);
  });

  it('treats a missing pathname as no route at all', () => {
    expect(parseOrgSettingsRoute(null).isOrgSettingsRoute).toBe(false);
    expect(parseOrgSettingsRoute(undefined).isOrgSettingsRoute).toBe(false);
  });
});
