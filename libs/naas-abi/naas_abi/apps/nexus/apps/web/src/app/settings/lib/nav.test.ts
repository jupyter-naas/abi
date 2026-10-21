import { describe, expect, it } from 'vitest';
import {
  parsePlatformSettingsRoute,
  platformSettingsGroups,
  platformSettingsSectionPath,
} from './nav';

describe('parsePlatformSettingsRoute', () => {
  it('parses the dashboard and table pages', () => {
    expect(parsePlatformSettingsRoute('/settings')).toEqual({
      isPlatformSettingsRoute: true,
      isDetail: false,
      section: null,
      sectionLabel: null,
      rowId: null,
    });
    expect(parsePlatformSettingsRoute('/settings/workspace_members')).toMatchObject({
      isDetail: true,
      section: 'workspace_members',
      sectionLabel: 'Workspace members',
    });
    expect(parsePlatformSettingsRoute('/settings/users/')).toMatchObject({
      section: 'users',
      sectionLabel: 'Users',
    });
  });

  it('parses row pages', () => {
    expect(parsePlatformSettingsRoute('/settings/users/user-48f0f9a98e27')).toMatchObject({
      isDetail: true,
      section: 'users',
      sectionLabel: 'Users',
      rowId: 'user-48f0f9a98e27',
    });
    expect(parsePlatformSettingsRoute('/settings/workspace_resource_policies/ws-1~maps').rowId).toBe(
      'ws-1~maps'
    );
    expect(parsePlatformSettingsRoute('/settings/users').rowId).toBeNull();
  });

  it('ignores workspace and organization settings', () => {
    expect(parsePlatformSettingsRoute('/workspace/ws-1/settings/members').isPlatformSettingsRoute).toBe(false);
    expect(parsePlatformSettingsRoute('/organizations/org-1/settings/users').isPlatformSettingsRoute).toBe(false);
    expect(parsePlatformSettingsRoute(null).isPlatformSettingsRoute).toBe(false);
  });
});

describe('platformSettingsGroups', () => {
  it('starts with the dashboard, then one group per section', () => {
    expect(platformSettingsGroups.map((group) => group.label)).toEqual([
      null,
      'People & access',
      'Sign-in & security',
      'Chat, agents & models',
      'Apps',
      'Code',
      'Maps',
      'Graph',
      'Ontology',
      'Search',
    ]);
    expect(platformSettingsGroups[0].items).toMatchObject([{ slug: '', label: 'Dashboard' }]);
    expect(platformSettingsGroups[1].items.map((item) => [item.slug, item.label])).toEqual([
      ['users', 'Users'],
      ['organizations', 'Organizations'],
      ['organization_members', 'Organization members'],
      ['organization_role_features', 'Organization role features'],
      ['workspaces', 'Workspaces'],
      ['workspace_members', 'Workspace members'],
      ['workspace_resource_policies', 'Workspace resource policies'],
    ]);
    expect(platformSettingsGroups[2].items).toContainEqual(
      expect.objectContaining({ slug: 'secrets_table', label: 'Secrets' })
    );
  });

  it('builds paths without a tables/ prefix', () => {
    expect(platformSettingsSectionPath('')).toBe('/settings');
    expect(platformSettingsSectionPath('users')).toBe('/settings/users');
  });
});
