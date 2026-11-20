import { describe, expect, it } from 'vitest';
import {
  isPlatformSettingsPath,
  PLATFORM_SETTINGS_SECTIONS,
  platformSettingsRedirect,
} from './redirects';
import { LEGACY_WORKSPACE_SETTINGS_SLUGS } from './tables';

describe('old table pages', () => {
  it('go to the same table under /settings/tables', () => {
    expect(platformSettingsRedirect('/settings/workspace_members')).toBe(
      '/settings/tables/workspace_members'
    );
    expect(platformSettingsRedirect('/settings/users/user-1')).toBe('/settings/tables/users/user-1');
    expect(platformSettingsRedirect('/settings/users/usr_1', '?x=1')).toBe('/settings/tables/users/usr_1?x=1');
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
    for (const path of [
      '/settings',
      '/settings/tables',
      '/settings/tables/users',
      '/settings/system',
      '/settings/system/jobs',
      '/settings/system/bus',
      '/settings/activity/traces',
      '/settings/resources/models',
      '/settings/data/documents',
      '/settings/roles',
    ]) {
      expect(platformSettingsRedirect(path)).toBeNull();
    }
    expect(platformSettingsRedirect('/settings/infrastructure')).toBeNull();
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
    ).toBe('/settings/activity/traces?trace=abc&span=d');
    expect(
      platformSettingsRedirect('/org/acme/workspace/ws-1/admin/system', '?tab=data&service=cache')
    ).toBe('/settings/data/cache');
  });

  it('send the Data page to the service page, and Live traffic, Traces and Events to Activity', () => {
    expect(platformSettingsRedirect('/settings/system/data')).toBe('/settings/data/knowledge-graph');
    expect(platformSettingsRedirect('/settings/system/data', '?service=email&item=m-1')).toBe(
      '/settings/resources/email?item=m-1'
    );
    expect(platformSettingsRedirect('/settings/system/traffic')).toBe('/settings/activity/traffic');
    expect(platformSettingsRedirect('/settings/system/traces/', '?trace=abc')).toBe(
      '/settings/activity/traces?trace=abc'
    );
    expect(platformSettingsRedirect('/settings/system/events')).toBe('/settings/activity/events');
    expect(platformSettingsRedirect('/settings/system/nats')).toBeNull();
  });

  it('send Access to Roles & permissions', () => {
    expect(platformSettingsRedirect('/workspace/ws-1/admin/system', '?tab=access')).toBe(
      '/settings/roles'
    );
    expect(platformSettingsRedirect('/settings/system/access')).toBe('/settings/roles');
  });

  it('send Modules & features, removed with the sets, to Roles & permissions', () => {
    expect(platformSettingsRedirect('/settings/modules')).toBe('/settings/roles');
    expect(platformSettingsRedirect('/settings/modules', '?org=acme')).toBe('/settings/roles?org=acme');
  });

  it('send the Console, removed, to Settings', () => {
    expect(platformSettingsRedirect('/settings/console')).toBe('/settings');
    expect(platformSettingsRedirect('/settings/console/')).toBe('/settings');
    expect(isPlatformSettingsPath('/settings/console')).toBe(false);
  });

  it('send Events to Activity › Events', () => {
    expect(platformSettingsRedirect('/workspace/ws-1/admin/events')).toBe('/settings/activity/events');
    expect(platformSettingsRedirect('/org/acme/workspace/ws-1/admin/events')).toBe(
      '/settings/activity/events'
    );
  });

  it('leave the rest of a workspace alone', () => {
    expect(platformSettingsRedirect('/workspace/ws-1/admin/services')).toBeNull();
    expect(platformSettingsRedirect('/workspace/ws-1/chat')).toBeNull();
  });
});

describe('PLATFORM_SETTINGS_SECTIONS', () => {
  it('is the first segment of each section path', () => {
    expect(PLATFORM_SETTINGS_SECTIONS).toEqual([
      'general',
      'tables',
      'system',
      'activity',
      'resources',
      'data',
      'organizations',
      'users',
      'roles',
      'drives',
    ]);
  });

  it('serves Create user at /settings/users/new, never redirected to a users row', () => {
    expect(platformSettingsRedirect('/settings/users/new')).toBeNull();
    expect(isPlatformSettingsPath('/settings/users/new')).toBe(true);
    expect(platformSettingsRedirect('/settings/users/usr_a')).toBe('/settings/tables/users/usr_a');
  });

  it('serves Users, never redirected to the users table (its rows still are)', () => {
    expect(platformSettingsRedirect('/settings/users')).toBeNull();
    expect(platformSettingsRedirect('/settings/users/')).toBeNull();
    expect(isPlatformSettingsPath('/settings/users')).toBe(true);
  });

  it('serves Drives, never sent to a workspace as a legacy link', () => {
    expect(platformSettingsRedirect('/settings/drives')).toBeNull();
    expect(isPlatformSettingsPath('/settings/drives')).toBe(true);
  });

  it('serves Organizations, never redirected to the organizations table', () => {
    expect(platformSettingsRedirect('/settings/organizations')).toBeNull();
    expect(platformSettingsRedirect('/settings/organization_members')).toBe(
      '/settings/tables/organization_members'
    );
  });
});

describe('isPlatformSettingsPath', () => {
  it('is the index and the sections', () => {
    expect(isPlatformSettingsPath('/settings')).toBe(true);
    expect(isPlatformSettingsPath('/settings/tables/users')).toBe(true);
    expect(isPlatformSettingsPath('/settings/system/events')).toBe(true);
    expect(isPlatformSettingsPath('/settings/activity/events')).toBe(true);
    expect(isPlatformSettingsPath('/settings/resources/models')).toBe(true);
    expect(isPlatformSettingsPath('/settings/data')).toBe(true);
    expect(isPlatformSettingsPath('/settings/roles')).toBe(true);
    expect(isPlatformSettingsPath('/settings/organizations')).toBe(true);
    expect(isPlatformSettingsPath('/settings/modules')).toBe(false);
    expect(isPlatformSettingsPath('/settings/members')).toBe(false);
    expect(isPlatformSettingsPath('/settings/tablesx')).toBe(false);
  });
});
