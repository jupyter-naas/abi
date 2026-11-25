import { describe, expect, it } from 'vitest';
import {
  DRIVES_ITEM,
  firstPlatformSettingsPath,
  holds,
  GENERAL_ITEM,
  laysOutOwnPanes,
  NEXUS_TABLES_ITEM,
  ORGANIZATIONS_ITEM,
  parsePlatformSettingsRoute,
  platformSettingsGroups,
  platformSettingsItemFor,
  ACCESS_ITEMS,
  USERS_ITEM,
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
];
const NEXUS_ACTIONS = ['nexus:ReadSystem', 'nexus:ListUsers', 'nexus:ListDrives'];
const none = (): PlatformActions =>
  Object.fromEntries([...IAM_ACTIONS, ...NEXUS_ACTIONS].map((action) => [action, false]));

const platformAdmin: PlatformActions = Object.fromEntries(
  [...IAM_ACTIONS, ...NEXUS_ACTIONS].map((action) => [action, true])
);
const delegatedIamAdmin: PlatformActions = { ...none(), 'iam:ListPolicies': true };
const systemReader: PlatformActions = { ...none(), 'nexus:ReadSystem': true };
const stranger: PlatformActions = none();
const userLister: PlatformActions = { ...none(), 'nexus:ListUsers': true };
const holdingsLister: PlatformActions = { ...none(), 'iam:ListAttachments': true };
const explainer: PlatformActions = { ...none(), 'iam:Explain': true };
const driveLister: PlatformActions = { ...none(), 'nexus:ListDrives': true };

const ids = (actions: PlatformActions | null) =>
  visiblePlatformSettingsGroups(actions).flatMap((group) => group.items.map((item) => item.id));

const GROUPS = ['Administration', 'Access', 'System', 'Activity', 'Resources', 'Data'];
const items = (label: string) =>
  (platformSettingsGroups.find((group) => group.label === label)?.items ?? []).map((item) => [
    item.label,
    item.href,
  ]);

describe('platformSettingsGroups', () => {
  it('is Administration, then Access, System, Activity, Resources and Data', () => {
    expect(platformSettingsGroups.map((group) => group.label)).toEqual(GROUPS);
    expect(items('Administration')).toEqual([
      ['General', '/settings/general'],
      ['Theme', '/settings/theme'],
      ['Organizations', '/settings/organizations'],
      ['Users', '/settings/users'],
    ]);
    expect(items('Access')).toEqual([
      ['Groups', '/settings/access/groups'],
      ['Policies', '/settings/access/policies'],
      ['Service accounts', '/settings/access/service-accounts'],
      ['Module approvals', '/settings/access/approvals'],
      ['Simulator', '/settings/access/simulator'],
      ['Audit', '/settings/access/audit'],
      ['Models', '/settings/models'],
    ]);
    expect(items('System')).toEqual([
      ['Overview', '/settings/system'],
      ['Services', '/settings/system/services'],
      ['Modules', '/settings/system/modules'],
      ['Discovery', '/settings/system/discovery'],
      ['Agents', '/settings/system/agents'],
      ['Jobs', '/settings/system/jobs'],
      ['NATS', '/settings/system/nats'],
      ['Bus', '/settings/system/bus'],
      ['Layers', '/settings/system/layers'],
      ['Diagrams', '/settings/system/diagrams'],
    ]);
    expect(items('Activity')).toEqual([
      ['Live traffic', '/settings/activity/traffic'],
      ['Traces', '/settings/activity/traces'],
      ['Events', '/settings/activity/events'],
      ['Event store', '/settings/activity/event-store'],
      ['Activity log', '/settings/activity/log'],
    ]);
    expect(items('Resources')).toEqual([
      ['Drives', '/settings/drives'],
      ['Models', '/settings/resources/models'],
      ['Secrets', '/settings/resources/secrets'],
      ['Email', '/settings/resources/email'],
      ['Source control', '/settings/resources/source-control'],
      ['Coding environments', '/settings/resources/coding-environments'],
    ]);
    expect(items('Data')).toEqual([
      ['Nexus tables', '/settings/tables'],
      ['Knowledge graph', '/settings/data/knowledge-graph'],
      ['Vector store', '/settings/data/vector-store'],
      ['Documents', '/settings/data/documents'],
      ['Datasets', '/settings/data/datasets'],
      ['Object storage', '/settings/data/object-storage'],
      ['Key-value', '/settings/data/key-value'],
      ['Cache', '/settings/data/cache'],
    ]);
  });

  it('gives every group a heading of its own (the layout keys groups by it)', () => {
    const labels = platformSettingsGroups.map((group) => group.label);
    expect(labels.every((label) => label.length > 0)).toBe(true);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it('gives every page one place, one id and one icon', () => {
    const all = platformSettingsGroups.flatMap((group) => group.items);
    expect(new Set(all.map((item) => item.id)).size).toBe(all.length);
    expect(new Set(all.map((item) => item.href)).size).toBe(all.length);
    expect(all.every((item) => item.icon)).toBe(true);
    expect(new Set(all.map((item) => item.icon)).size).toBe(all.length);
  });

  it('needs nexus:ListUsers or iam:ListAttachments for Users, nexus:ListDrives for Drives, its own IAM actions for each Access page, nexus:ReadSystem for the rest', () => {
    const access: Record<string, string[]> = {
      'access-policies': ['iam:ListPolicies', 'iam:CreatePolicy', 'iam:ListAttachments'],
      'access-groups': ['iam:ListGroups'],
      'access-service-accounts': ['iam:ListPrincipals'],
      'access-approvals': ['iam:ListManifests'],
      'access-simulator': ['iam:Explain'],
      'access-audit': ['nexus:ReadSystem'],
    };
    const single: Record<string, string> = { drives: 'nexus:ListDrives', models: 'iam:ListPolicies' };
    for (const item of platformSettingsGroups.flatMap((group) => group.items)) {
      const expected =
        item.id === 'users'
          ? { anyOf: ['nexus:ListUsers', 'iam:ListAttachments'] }
          : single[item.id]
            ? { action: single[item.id] }
            : access[item.id]
            ? { anyOf: access[item.id] }
            : { action: 'nexus:ReadSystem' };
      expect(item.needs).toEqual(expected);
    }
  });
});

describe('what the caller sees', () => {
  it('shows a platform admin everything, General first', () => {
    expect(ids(platformAdmin)).toHaveLength(40);
    expect(ids(platformAdmin)).toContain('users');
    expect(ids(platformAdmin)).toContain('drives');
    expect(visiblePlatformSettingsGroups(platformAdmin).map((group) => group.label)).toEqual(GROUPS);
    expect(firstPlatformSettingsPath(platformAdmin)).toBe('/settings/general');
  });

  it('shows a delegated IAM admin without nexus:ReadSystem only the Access pages IAM opens to them', () => {
    expect(ids(delegatedIamAdmin)).toEqual(['access-policies', 'models']);
    expect(visiblePlatformSettingsGroups(delegatedIamAdmin).map((group) => group.label)).toEqual(['Access']);
    expect(firstPlatformSettingsPath(delegatedIamAdmin)).toBe('/settings/access/policies');
    expect(ids(explainer)).toEqual(['access-simulator']);
  });

  it('shows whoever may list who holds what Users (the people who hold something) and Policies', () => {
    expect(ids(holdingsLister)).toEqual(['users', 'access-policies']);
    expect(firstPlatformSettingsPath(holdingsLister)).toBe('/settings/users');
  });

  it('shows a reader of the system everything but Users and the IAM pages of Access, its Audit included', () => {
    expect(ids(systemReader).filter((id) => id.startsWith('access-'))).toEqual(['access-audit']);
    expect(ids(systemReader)).not.toContain('users');
    expect(ids(systemReader)).not.toContain('drives');
    expect(ids(systemReader)).toContain('tables');
    expect(ids(systemReader)).toContain('system-events');
    expect(ids(systemReader)).toContain('service-triple_store');
    expect(ids(systemReader)).toEqual(expect.arrayContaining(['system-layers', 'system-diagrams']));
    const groups = visiblePlatformSettingsGroups(systemReader);
    expect(groups.map((group) => group.label)).toEqual(GROUPS);
    expect(groups[0].items.map((item) => item.label)).toEqual(['General', 'Theme', 'Organizations']);
    expect(groups[1].items.map((item) => item.label)).toEqual(['Audit']);
  });

  it('shows Users to whoever IAM lets list the users, and nothing else to them', () => {
    expect(ids(userLister)).toEqual(['users']);
    expect(visiblePlatformSettingsGroups(userLister).map((group) => group.label)).toEqual(['Administration']);
    expect(firstPlatformSettingsPath(userLister)).toBe('/settings/users');
  });

  it('shows Drives to whoever IAM lets list the drives, and nothing else to them', () => {
    expect(ids(driveLister)).toEqual(['drives']);
    expect(visiblePlatformSettingsGroups(driveLister).map((group) => group.label)).toEqual(['Resources']);
    expect(firstPlatformSettingsPath(driveLister)).toBe('/settings/drives');
  });

  it('shows a stranger nothing: the 403', () => {
    expect(ids(stranger)).toEqual([]);
    expect(ids({})).toEqual([]);
    expect(ids(null)).toEqual([]);
    expect(visiblePlatformSettingsGroups(stranger)).toEqual([]);
    expect(firstPlatformSettingsPath(stranger)).toBeNull();
  });

  it('opens an Access page on any of its actions, nothing else', () => {
    const policies = ACCESS_ITEMS.find((item) => item.id === 'access-policies')!.needs;
    expect(holds(policies, { 'nexus:ReadSystem': true, 'iam:Explain': true })).toBe(false);
    expect(holds(policies, { 'iam:CreatePolicy': true })).toBe(true);
    expect(holds(policies, { 'iam:ListAttachments': true })).toBe(true);
    expect(holds(policies, { 'iam:ListPolicies': false })).toBe(false);
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

  it('parses System, Activity and service pages, the Access pages and a person under Users', () => {
    expect(parsePlatformSettingsRoute('/settings/system').item?.id).toBe('system-overview');
    expect(parsePlatformSettingsRoute('/settings/system/jobs').item?.id).toBe('system-jobs');
    expect(parsePlatformSettingsRoute('/settings/activity/events').item?.id).toBe('system-events');
    expect(parsePlatformSettingsRoute('/settings/system/bus').item?.id).toBe('service-bus');
    expect(parsePlatformSettingsRoute('/settings/resources/models').item?.id).toBe('service-model_registry');
    expect(parsePlatformSettingsRoute('/settings/data/documents').item?.id).toBe('service-document');
    expect(parsePlatformSettingsRoute('/settings/access/policies').item?.id).toBe('access-policies');
    expect(parsePlatformSettingsRoute('/settings/access/policies/builtin.owner').item?.id).toBe('access-policies');
    expect(parsePlatformSettingsRoute('/settings/access/groups/grp_1').item?.id).toBe('access-groups');
    expect(parsePlatformSettingsRoute('/settings/users/usr_1').item?.id).toBe('users');
    expect(parsePlatformSettingsRoute('/settings/roles').item).toBeNull();
    expect(parsePlatformSettingsRoute('/settings/organizations').item?.id).toBe('organizations');
    expect(parsePlatformSettingsRoute('/settings/users').item?.id).toBe('users');
    expect(parsePlatformSettingsRoute('/settings/drives').item?.id).toBe('drives');
    expect(parsePlatformSettingsRoute('/settings/system/jobs').table).toBeNull();
  });

  it('ignores workspace and organization settings', () => {
    expect(parsePlatformSettingsRoute('/workspace/ws-1/settings/users').isPlatformSettingsRoute).toBe(false);
    expect(parsePlatformSettingsRoute('/organizations/org-1/settings/users').isPlatformSettingsRoute).toBe(false);
    expect(parsePlatformSettingsRoute(null).isPlatformSettingsRoute).toBe(false);
  });

  it('matches the longest item', () => {
    expect(platformSettingsItemFor('/settings/activity/traces?trace=abc')?.id).toBe('system-traces');
    expect(platformSettingsItemFor('/settings/data/documents?item=ns%2Fa')?.id).toBe('service-document');
    expect(platformSettingsItemFor('/settings/systemic')).toBeNull();
    expect(platformSettingsItemFor('/settings')).toBeNull();
  });
});

describe('laysOutOwnPanes', () => {
  it('keeps the margins of the organization pages on every Administration page', () => {
    expect(laysOutOwnPanes(GENERAL_ITEM)).toBe(false);
    expect(laysOutOwnPanes(ORGANIZATIONS_ITEM)).toBe(false);
    expect(laysOutOwnPanes(USERS_ITEM)).toBe(false);
    for (const item of ACCESS_ITEMS) expect(laysOutOwnPanes(item)).toBe(false);
    expect(laysOutOwnPanes(DRIVES_ITEM)).toBe(false);
  });

  it('lets the System pages lay out their own panes', () => {
    expect(laysOutOwnPanes({ id: 'overview' })).toBe(true);
  });

  it('leaves Nexus tables to their own layout', () => {
    expect(laysOutOwnPanes(NEXUS_TABLES_ITEM)).toBe(false);
  });
});
