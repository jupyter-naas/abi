import { describe, expect, it } from 'vitest';
import {
  SETTINGS_GROUPS,
  settingsItemFor,
  settingsItemShown,
  settingsLandingPath,
  settingsPageOpens,
  visibleSettingsGroups,
  workspaceSettingsAccess,
} from '@/components/shell/settings-nav';
import { describeModuleResources, type WorkspaceResources } from '@/lib/workspace-resources';

function resources(over: Partial<WorkspaceResources> = {}): WorkspaceResources {
  return {
    organization_id: 'org-1',
    features: ['agents', 'apps', 'files', 'graph', 'maps', 'ontology', 'search', 'skills', 'settings'],
    modules: [],
    totals: { agents: 2, apps: 1, workflows: 0, pipelines: 1 },
    ...over,
  };
}

const IAM = { actions: { 'iam:ListPolicies': true, 'iam:ListGroups': true } };

const labels = (groups: ReturnType<typeof visibleSettingsGroups>) =>
  groups.flatMap((group) => group.items.map((item) => item.label));

describe('workspace settings nav', () => {
  it('lists every entry the caller may use', () => {
    expect(
      labels(visibleSettingsGroups(resources(), undefined, SETTINGS_GROUPS, { access: IAM, readsAnalytics: true }))
    ).toEqual(
      SETTINGS_GROUPS.flatMap((group) => group.items.map((item) => item.label))
    );
  });

  it('has no Drives: they are listed in Platform Settings › Drives', () => {
    const all = SETTINGS_GROUPS.flatMap((group) => group.items);
    expect(all.map((item) => item.label)).not.toContain('Drives');
    expect(settingsItemFor('/workspace/ws-1/settings/drives')).toBeUndefined();
  });

  it('shows Access › Policies and Groups only to whoever IAM lets open each there, Members to everyone', () => {
    const shown = (actions: Record<string, boolean> | null) =>
      labels(visibleSettingsGroups(resources(), undefined, SETTINGS_GROUPS, { access: actions && { actions } }));
    expect(shown(null)).not.toContain('Policies');
    expect(shown(null)).not.toContain('Groups');
    expect(shown(null)).toContain('Users');
    expect(shown({ 'iam:ListPolicies': true })).toContain('Policies');
    expect(shown({ 'iam:ListPolicies': true })).not.toContain('Groups');
    expect(shown({ 'iam:ListAttachments': true })).toContain('Policies');
    expect(shown({ 'iam:ListGroups': true })).toEqual(expect.arrayContaining(['Groups']));
    expect(shown({ 'iam:Explain': true, 'nexus:ReadSystem': true })).not.toContain('Policies');
    const access = visibleSettingsGroups(null, undefined, SETTINGS_GROUPS, { access: IAM }).find((g) => g.label === 'Access');
    expect(access?.items.map((item) => [item.label, item.href])).toEqual([
      ['Groups', '/settings/groups'],
      ['Policies', '/settings/policies'],
    ]);
    expect(labels(visibleSettingsGroups(resources(), undefined, SETTINGS_GROUPS, { access: IAM }))).not.toContain('Roles & permissions');
  });

  it('lists Analytics and Access for a role that opens settings until their reads answer', () => {
    const pending = labels(
      visibleSettingsGroups(resources(), undefined, SETTINGS_GROUPS, {
        roleOpens: true,
        accessKnown: false,
        analyticsKnown: false,
      })
    );
    expect(pending).toEqual(expect.arrayContaining(['Analytics', 'Groups', 'Policies']));
    const denied = labels(
      visibleSettingsGroups(resources(), undefined, SETTINGS_GROUPS, {
        roleOpens: true,
        access: { actions: {} },
        readsAnalytics: false,
        accessKnown: true,
        analyticsKnown: true,
      })
    );
    expect(denied).not.toContain('Analytics');
    expect(denied).not.toContain('Groups');
    expect(denied).not.toContain('Policies');
  });

  it('shows Analytics, in the General group, only to whoever may read the workspace analytics', () => {
    expect(labels(visibleSettingsGroups(resources()))).not.toContain('Analytics');
    expect(labels(visibleSettingsGroups(resources(), undefined, SETTINGS_GROUPS, { access: IAM }))).not.toContain(
      'Analytics'
    );
    const groups = visibleSettingsGroups(null, undefined, SETTINGS_GROUPS, { readsAnalytics: true });
    expect(groups.find((group) => group.label === 'General')?.items.map((item) => item.label)).toContain('Analytics');
    expect(settingsItemFor('/workspace/ws-1/settings/analytics')?.needs).toBe('analytics');
  });

  it('opens Analytics to whoever the role brings the settings, never to an iam:-only holder', () => {
    expect(settingsPageOpens('all', '/workspace/ws-1/settings/analytics')).toBe(true);
    expect(settingsPageOpens('iam', '/workspace/ws-1/settings/analytics')).toBe(false);
    expect(settingsPageOpens('none', '/workspace/ws-1/settings/analytics')).toBe(false);
  });

  it('hides an entry whose feature the caller does not hold', () => {
    const shown = labels(visibleSettingsGroups(resources({ features: ['apps', 'settings'] })));
    expect(shown).toContain('Apps');
    expect(shown).not.toContain('Agents');
    expect(shown).not.toContain('Maps');
    // No feature: always there.
    expect(shown).toContain('Models');
    expect(shown).toContain('General');
    // Features (General) and Files (Features): Files is where Workspace Files is turned on.
    expect(shown).toContain('Features');
    expect(shown).toContain('Files');
  });

  it('hides Apps and Workflows when the caller may use none of theirs', () => {
    const none = { agents: 0, apps: 0, workflows: 0, pipelines: 0 };
    const shown = labels(visibleSettingsGroups(resources({ totals: none })));
    expect(shown).not.toContain('Apps');
    expect(shown).not.toContain('Workflows');
    // Agents the workspace builds itself stay manageable.
    expect(shown).toContain('Agents');
    const pipelines = labels(visibleSettingsGroups(resources({ totals: { ...none, pipelines: 2 } })));
    expect(pipelines).toContain('Workflows');
  });

  it('never hides an entry for a kind whose source did not answer', () => {
    const none = { agents: 0, apps: 0, workflows: 0, pipelines: 0 };
    const down = resources({ totals: none, unavailable: ['workflows', 'pipelines'] });
    const shown = labels(visibleSettingsGroups(down));
    // The jobs did not answer: Workflows stays; Apps, answered with none, does not.
    expect(shown).toContain('Workflows');
    expect(shown).not.toContain('Apps');
    expect(settingsItemShown(settingsItemFor('/workspace/ws-1/settings/workflows')!, down)).toBe(true);
  });

  it('follows the caller flags while the resources are unknown', () => {
    const shown = labels(visibleSettingsGroups(null, { apps: false, maps: true }));
    expect(shown).not.toContain('Apps');
    expect(shown).toContain('Maps');
    expect(shown).toContain('Workflows');
  });

  it('finds the entry of a path, nested pages included', () => {
    expect(settingsItemFor('/workspace/ws-1/settings/apps')?.label).toBe('Apps');
    expect(settingsItemFor('/workspace/ws-1/settings/agents/a-1')?.label).toBe('Agents');
    expect(settingsItemFor('/workspace/ws-1/chat')).toBeUndefined();
  });

  it('has no Infrastructure: the map of the code is the platform\'s, in Platform › System', () => {
    expect(visibleSettingsGroups(null).map((group) => group.label)).toEqual(['General', 'Features']);
    expect(settingsItemFor('/workspace/ws-1/settings/infrastructure/layers')).toBeUndefined();
  });

  it('describes a module by what the caller may use of it', () => {
    expect(
      describeModuleResources({ module: 'p', agents: 2, apps: 1, workflows: 0, pipelines: 1 })
    ).toBe('2 agents · 1 app · 1 pipeline');
  });
});


describe('who opens a workspace\'s settings (UJ-W1)', () => {
  it('opens every page to whoever the role there brings the settings, at once', () => {
    const access = workspaceSettingsAccess({ settingsByRole: true, holdsIam: false, accessSettled: false });
    expect(access).toBe('all');
    expect(settingsPageOpens(access, '/workspace/ws-1/settings/general')).toBe(true);
    expect(settingsLandingPath(access)).toBe('/settings/general');
  });

  it('opens the Access pages IAM opens, and a member’s page, alone to someone IAM shows one of them', () => {
    const access = workspaceSettingsAccess({ settingsByRole: false, holdsIam: true, accessSettled: true });
    expect(access).toBe('iam');
    const policies = { actions: { 'iam:ListPolicies': true } };
    expect(settingsPageOpens(access, '/workspace/ws-1/settings/policies', undefined, policies)).toBe(true);
    expect(settingsPageOpens(access, '/workspace/ws-1/settings/policies/pol_1', undefined, policies)).toBe(true);
    expect(settingsPageOpens(access, '/workspace/ws-1/settings/groups', undefined, policies)).toBe(false);
    expect(settingsPageOpens(access, '/workspace/ws-1/settings/users/usr_bob', undefined, policies)).toBe(true);
    expect(settingsPageOpens(access, '/workspace/ws-1/settings/users', undefined, policies)).toBe(false);
    expect(settingsPageOpens(access, '/workspace/ws-1/settings/general', undefined, policies)).toBe(false);
    expect(settingsLandingPath(access, policies)).toBe('/settings/policies');
    expect(settingsLandingPath(access, { actions: { 'iam:ListGroups': true } })).toBe('/settings/groups');
    // Policies while IAM's answer is read.
    expect(settingsLandingPath(access)).toBe('/settings/policies');
  });

  it('opens nothing to a member with neither (Dave), and decides nothing before the access is read', () => {
    expect(workspaceSettingsAccess({ settingsByRole: false, holdsIam: false, accessSettled: false })).toBe('unknown');
    expect(settingsPageOpens('unknown', '/workspace/ws-1/settings/general')).toBeNull();
    const access = workspaceSettingsAccess({ settingsByRole: false, holdsIam: false, accessSettled: true });
    expect(access).toBe('none');
    for (const page of ['general', 'members', 'policies', 'groups', 'members/usr_bob', 'agents']) {
      expect(settingsPageOpens(access, `/workspace/ws-1/settings/${page}`)).toBe(false);
    }
  });
});
