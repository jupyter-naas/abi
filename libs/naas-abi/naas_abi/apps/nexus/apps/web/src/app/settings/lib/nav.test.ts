import { describe, expect, it } from 'vitest';
import {
  firstPlatformSettingsPath,
  holds,
  parsePlatformSettingsRoute,
  platformSettingsGroups,
  platformSettingsItemFor,
  visiblePlatformSettingsGroups,
  type PlatformActions,
} from './nav';

// As GET /api/iam/admin/access answers them (services/iam_admin ACCESS_ACTIONS + ReadSystem).
const IAM_ACTIONS = [
  'iam:ListPolicies',
  'iam:CreatePolicy',
  'iam:ListGroups',
  'iam:ListAttachments',
  'iam:ListPrincipals',
  'iam:ListManifests',
  'iam:Explain',
  'iam:GetSet',
];
const none = (): PlatformActions =>
  Object.fromEntries([...IAM_ACTIONS, 'nexus:ReadSystem'].map((action) => [action, false]));

const platformAdmin: PlatformActions = Object.fromEntries(
  [...IAM_ACTIONS, 'nexus:ReadSystem'].map((action) => [action, true])
);
const delegatedIamAdmin: PlatformActions = { ...none(), 'iam:ListPolicies': true };
const systemReader: PlatformActions = { ...none(), 'nexus:ReadSystem': true };
const stranger: PlatformActions = none();

const ids = (actions: PlatformActions | null) =>
  visiblePlatformSettingsGroups(actions).flatMap((group) => group.items.map((item) => item.id));

describe('platformSettingsGroups', () => {
  it('is Nexus tables, then System, then Roles & permissions and Modules & features', () => {
    expect(platformSettingsGroups.map((group) => group.label)).toEqual([null, 'System', 'Access']);
    expect(platformSettingsGroups[0].items.map((item) => [item.label, item.href])).toEqual([
      ['Nexus tables', '/settings/tables'],
    ]);
    expect(platformSettingsGroups[1].items.map((item) => [item.label, item.href])).toEqual([
      ['Overview', '/settings/system'],
      ['Services', '/settings/system/services'],
      ['Data', '/settings/system/data'],
      ['Jobs', '/settings/system/jobs'],
      ['Agents', '/settings/system/agents'],
      ['Modules', '/settings/system/modules'],
      ['NATS', '/settings/system/nats'],
      ['Live traffic', '/settings/system/traffic'],
      ['Traces', '/settings/system/traces'],
      ['Events', '/settings/system/events'],
    ]);
    expect(platformSettingsGroups[2].items.map((item) => [item.label, item.href])).toEqual([
      ['Roles & permissions', '/settings/roles'],
      ['Modules & features', '/settings/modules'],
    ]);
  });

  it('needs nexus:ReadSystem for the tables and System, any iam: action for Roles & permissions', () => {
    for (const item of [...platformSettingsGroups[0].items, ...platformSettingsGroups[1].items]) {
      expect(item.needs).toEqual({ action: 'nexus:ReadSystem' });
    }
    expect(platformSettingsGroups[2].items[0].needs).toEqual({ anyOf: 'iam' });
    expect(platformSettingsGroups[2].items[1].needs).toEqual({ action: 'iam:GetSet' });
  });
});

describe('what the caller sees', () => {
  it('shows a platform admin everything', () => {
    expect(ids(platformAdmin)).toHaveLength(13);
    expect(firstPlatformSettingsPath(platformAdmin)).toBe('/settings/tables');
  });

  it('shows a delegated IAM admin without nexus:ReadSystem only Roles & permissions', () => {
    expect(ids(delegatedIamAdmin)).toEqual(['roles']);
    expect(visiblePlatformSettingsGroups(delegatedIamAdmin).map((group) => group.label)).toEqual([
      'Access',
    ]);
    expect(firstPlatformSettingsPath(delegatedIamAdmin)).toBe('/settings/roles');
  });

  it('shows Modules & features to whoever may read the sets', () => {
    expect(ids({ ...none(), 'iam:GetSet': true })).toEqual(['roles', 'modules']);
    expect(ids(delegatedIamAdmin)).not.toContain('modules');
  });

  it('shows a reader of the system the tables and System, not Roles & permissions', () => {
    expect(ids(systemReader)).not.toContain('roles');
    expect(ids(systemReader)).toContain('tables');
    expect(ids(systemReader)).toContain('system-events');
  });

  it('shows a stranger nothing: the 403', () => {
    expect(ids(stranger)).toEqual([]);
    expect(ids({})).toEqual([]);
    expect(ids(null)).toEqual([]);
    expect(firstPlatformSettingsPath(stranger)).toBeNull();
  });

  it('counts only iam: actions for Roles & permissions', () => {
    expect(holds({ anyOf: 'iam' }, { 'nexus:ReadSystem': true })).toBe(false);
    expect(holds({ anyOf: 'iam' }, { 'iam:Explain': true })).toBe(true);
    expect(holds({ anyOf: 'iam' }, { 'iam:Explain': false })).toBe(false);
  });
});

describe('parsePlatformSettingsRoute', () => {
  it('parses the index', () => {
    expect(parsePlatformSettingsRoute('/settings')).toEqual({
      isPlatformSettingsRoute: true,
      isDetail: false,
      item: null,
      table: null,
      rowId: null,
    });
  });

  it('parses Nexus tables, a table and a row', () => {
    expect(parsePlatformSettingsRoute('/settings/tables')).toMatchObject({
      isDetail: true,
      item: { id: 'tables' },
      table: null,
    });
    expect(parsePlatformSettingsRoute('/settings/tables/workspace_members/')).toMatchObject({
      item: { id: 'tables' },
      table: 'workspace_members',
      rowId: null,
    });
    expect(
      parsePlatformSettingsRoute('/settings/tables/workspace_resource_policies/ws-1~maps')
    ).toMatchObject({ table: 'workspace_resource_policies', rowId: 'ws-1~maps' });
    expect(parsePlatformSettingsRoute('/settings/tables/secrets/a%2Fb').rowId).toBe('a/b');
  });

  it('parses System pages and Roles & permissions', () => {
    expect(parsePlatformSettingsRoute('/settings/system').item?.id).toBe('system-overview');
    expect(parsePlatformSettingsRoute('/settings/system/jobs').item?.id).toBe('system-jobs');
    expect(parsePlatformSettingsRoute('/settings/system/events').item?.id).toBe('system-events');
    expect(parsePlatformSettingsRoute('/settings/roles').item?.id).toBe('roles');
    expect(parsePlatformSettingsRoute('/settings/modules').item?.id).toBe('modules');
    expect(parsePlatformSettingsRoute('/settings/system/jobs').table).toBeNull();
  });

  it('ignores workspace and organization settings', () => {
    expect(parsePlatformSettingsRoute('/workspace/ws-1/settings/members').isPlatformSettingsRoute).toBe(false);
    expect(parsePlatformSettingsRoute('/organizations/org-1/settings/users').isPlatformSettingsRoute).toBe(false);
    expect(parsePlatformSettingsRoute(null).isPlatformSettingsRoute).toBe(false);
  });

  it('matches the longest item', () => {
    expect(platformSettingsItemFor('/settings/system/traces?trace=abc')?.id).toBe('system-traces');
    expect(platformSettingsItemFor('/settings/systemic')).toBeNull();
    expect(platformSettingsItemFor('/settings')).toBeNull();
  });
});
