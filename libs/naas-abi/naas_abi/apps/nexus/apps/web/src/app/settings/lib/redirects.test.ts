import { describe, expect, it } from 'vitest';
import { isPlatformSettingsPath, platformSettingsRedirect } from './redirects';
import { LEGACY_WORKSPACE_SETTINGS_SLUGS } from './tables';

describe('old table pages', () => {
  it('go to the same table under /settings/tables', () => {
    expect(platformSettingsRedirect('/settings/users')).toBe('/settings/tables/users');
    expect(platformSettingsRedirect('/settings/workspace_members')).toBe(
      '/settings/tables/workspace_members'
    );
    expect(platformSettingsRedirect('/settings/users/user-1')).toBe('/settings/tables/users/user-1');
    expect(platformSettingsRedirect('/settings/workspace_resource_policies/ws-1~maps')).toBe(
      '/settings/tables/workspace_resource_policies/ws-1~maps'
    );
  });

  it('drop the suffix a table named like a workspace settings path had', () => {
    expect(platformSettingsRedirect('/settings/secrets_table')).toBe('/settings/tables/secrets');
    expect(platformSettingsRedirect('/settings/ontologies_table/o-1')).toBe(
      '/settings/tables/ontologies/o-1'
    );
  });

  it('leave the sections, the index and legacy workspace links alone', () => {
    for (const path of ['/settings', '/settings/tables', '/settings/tables/users', '/settings/system', '/settings/system/jobs', '/settings/roles']) {
      expect(platformSettingsRedirect(path)).toBeNull();
    }
    for (const slug of LEGACY_WORKSPACE_SETTINGS_SLUGS) {
      expect(platformSettingsRedirect(`/settings/${slug}`)).toBeNull();
    }
  });
});

describe('old System links', () => {
  it('open the tab as its page, its query kept', () => {
    expect(platformSettingsRedirect('/workspace/ws-1/admin/system')).toBe('/settings/system');
    expect(platformSettingsRedirect('/workspace/ws-1/admin/system', '?tab=nats')).toBe(
      '/settings/system/nats'
    );
    expect(
      platformSettingsRedirect('/workspace/ws-1/admin/system', '?tab=traces&trace=abc&span=d')
    ).toBe('/settings/system/traces?trace=abc&span=d');
    expect(
      platformSettingsRedirect('/org/acme/workspace/ws-1/admin/system', '?tab=data&service=cache')
    ).toBe('/settings/system/data?service=cache');
  });

  it('send Access to Roles & permissions', () => {
    expect(platformSettingsRedirect('/workspace/ws-1/admin/system', '?tab=access')).toBe(
      '/settings/roles'
    );
    expect(platformSettingsRedirect('/settings/system/access')).toBe('/settings/roles');
  });

  it('send Events to System › Events', () => {
    expect(platformSettingsRedirect('/workspace/ws-1/admin/events')).toBe('/settings/system/events');
    expect(platformSettingsRedirect('/org/acme/workspace/ws-1/admin/events')).toBe(
      '/settings/system/events'
    );
  });

  it('leave the rest of a workspace alone', () => {
    expect(platformSettingsRedirect('/workspace/ws-1/admin/services')).toBeNull();
    expect(platformSettingsRedirect('/workspace/ws-1/chat')).toBeNull();
  });
});

describe('isPlatformSettingsPath', () => {
  it('is the index and the three sections', () => {
    expect(isPlatformSettingsPath('/settings')).toBe(true);
    expect(isPlatformSettingsPath('/settings/tables/users')).toBe(true);
    expect(isPlatformSettingsPath('/settings/system/events')).toBe(true);
    expect(isPlatformSettingsPath('/settings/roles')).toBe(true);
    expect(isPlatformSettingsPath('/settings/members')).toBe(false);
    expect(isPlatformSettingsPath('/settings/tablesx')).toBe(false);
  });
});
