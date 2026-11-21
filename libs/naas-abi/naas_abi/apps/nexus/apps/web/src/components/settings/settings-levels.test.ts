import { describe, expect, it } from 'vitest';
import { accountSettingsNavVisible } from '@/app/account/lib/nav';
import { orgSettingsNavForRole } from '@/app/organizations/[orgId]/settings/lib/nav';
import { visiblePlatformSettingsGroups } from '@/app/settings/lib/nav';
import { SETTINGS_GROUPS } from '@/components/shell/settings-nav';
import {
  activeSettingsHref,
  currentSettingsLevel,
  settingsLevels,
  settingsTabs,
  type SettingsLevelsInput,
} from './settings-levels';

const member: SettingsLevelsInput = {
  account: accountSettingsNavVisible,
  workspace: null,
  organization: null,
  otherOrganizations: [],
  platform: [],
};

const titles = (input: SettingsLevelsInput) => settingsLevels(input).map((level) => level.label);
const labels = (input: SettingsLevelsInput, id: string) =>
  settingsLevels(input)
    .find((level) => level.id === id)
    ?.groups.flatMap((group) => group.links.map((link) => link.label)) ?? [];

const all: SettingsLevelsInput = {
  ...member,
  workspace: { id: 'ws-1', groups: SETTINGS_GROUPS },
  organization: { id: 'acme', name: 'Acme', items: orgSettingsNavForRole('admin', { access: { actions: { 'iam:ListPolicies': true, 'iam:ListGroups': true } } }), current: true },
  platform: visiblePlatformSettingsGroups({ 'nexus:ReadSystem': true, 'nexus:ListUsers': true }),
};

describe('the levels of Settings', () => {
  it('shows a member their account alone', () => {
    expect(titles(member)).toEqual(['Account']);
  });

  it('goes from the widest level to the narrowest, each with only what the caller opens', () => {
    expect(titles(all)).toEqual(['Platform', 'Organization', 'Workspace', 'Account']);
    expect(labels(all, 'organization')).toContain('Users');
    expect(labels(all, 'platform')).toEqual(expect.arrayContaining(['General', 'Organizations', 'Users', 'Jobs']));
    expect(labels(all, 'platform')).not.toContain('Roles & permissions');
    expect(labels(all, 'organization')).toEqual(expect.arrayContaining(['Users', 'Policies', 'Groups']));
    expect(labels(all, 'organization')).not.toContain('Roles & permissions');
  });

  it('puts the organization’s Access pages under their own heading, after its pages', () => {
    const organization = settingsLevels(all).find((level) => level.id === 'organization');
    expect(organization?.groups.map((group) => group.label)).toEqual([null, 'Access']);
    expect(organization?.groups[1].links.map((link) => [link.label, link.href])).toEqual([
      ['Groups', '/organizations/acme/settings/groups'],
      ['Policies', '/organizations/acme/settings/policies'],
    ]);
  });

  it('keeps every group of the platform, each under its heading, Layers and Diagrams in System', () => {
    const platform = settingsLevels(all).find((level) => level.id === 'platform');
    expect(platform?.groups.map((group) => group.label)).toEqual(['Administration', 'Access', 'System', 'Activity', 'Resources', 'Data']);
    expect(platform?.groups[1].links.map((link) => link.label)).toEqual(['Audit']);
    expect(platform?.groups[2].links.map((link) => link.label)).toEqual(expect.arrayContaining(['Layers', 'Diagrams']));
    const usersOnly = settingsLevels({ ...member, platform: visiblePlatformSettingsGroups({ 'nexus:ListUsers': true }) });
    expect(usersOnly[0].groups).toMatchObject([{ label: 'Administration', links: [{ label: 'Users' }] }]);
  });

  it('roots the workspace pages at the workspace, its later groups named under the level', () => {
    const [workspace] = settingsLevels({ ...member, workspace: { id: 'ws-1', groups: SETTINGS_GROUPS } });
    expect(workspace.groups.map((group) => group.label)).toEqual([null, 'Access', 'Features']);
    expect(workspace.groups[0].links[0].href).toBe('/workspace/ws-1/settings/general');
    expect(workspace.index).toBe('/workspace/ws-1/settings');
  });

  it('leaves a level out when the caller opens nothing there', () => {
    const input: SettingsLevelsInput = {
      ...member,
      workspace: { id: 'ws-1', groups: [{ label: 'General', items: [] }] },
      organization: { id: 'acme', name: 'Acme', items: [], current: true },
      platform: [{ label: 'Administration', items: [] }],
    };
    expect(titles(input)).toEqual(['Account']);
  });

  it('names the organization when the caller opens several, and links the others', () => {
    const input: SettingsLevelsInput = {
      ...member,
      organization: { id: 'acme', name: 'Acme', items: orgSettingsNavForRole('admin', { access: null }), current: true },
      otherOrganizations: [{ id: 'beta', name: 'Beta' }],
    };
    const organization = settingsLevels(input).find((level) => level.id === 'organization');
    expect(organization?.label).toBe('Organization · Acme');
    expect(organization?.groups.at(-1)).toMatchObject({
      label: 'Other organizations',
      links: [{ label: 'Beta', href: '/organizations/beta/settings' }],
    });
  });

  it('names the organization when it is not the current workspace\'s', () => {
    const items = orgSettingsNavForRole('admin', { access: null });
    const elsewhere = { ...member, organization: { id: 'acme', name: 'Acme', items, current: false } };
    const here = { ...member, organization: { id: 'acme', name: 'Acme', items, current: true } };
    expect(titles(elsewhere)).toEqual(['Organization · Acme', 'Account']);
    expect(titles(here)).toEqual(['Organization', 'Account']);
  });

  it('lists the organizations when none is the page\'s or the workspace\'s', () => {
    const input = { ...member, otherOrganizations: [{ id: 'acme', name: 'Acme' }, { id: 'beta', name: 'Beta' }] };
    expect(titles(input)).toEqual(['Organizations', 'Account']);
  });

  it('marks the link a page is, or is under, the longest first', () => {
    const levels = settingsLevels({ ...member, workspace: { id: 'ws-1', groups: SETTINGS_GROUPS } });
    expect(activeSettingsHref(levels, '/workspace/ws-1/settings/agents/a-1')).toBe('/workspace/ws-1/settings/agents');
    expect(activeSettingsHref(levels, '/account/profile?tab=x')).toBe('/account/profile');
    expect(activeSettingsHref(levels, '/workspace/ws-1/chat')).toBeNull();
  });
});

describe('the level the column lists', () => {
  it('is the page\'s', () => {
    const levels = settingsLevels(all);
    expect(currentSettingsLevel(levels, '/settings/system/jobs')?.id).toBe('platform');
    expect(currentSettingsLevel(levels, '/organizations/acme/settings/members')?.id).toBe('organization');
    expect(currentSettingsLevel(levels, '/workspace/ws-1/settings/agents')?.id).toBe('workspace');
    expect(currentSettingsLevel(levels, '/account')?.id).toBe('account');
  });

  it('is the only level there is, on a page the caller may not open', () => {
    expect(currentSettingsLevel(settingsLevels(member), '/settings/users')?.id).toBe('account');
  });

  it('is none on a page whose level the caller does not open, among several', () => {
    const levels = settingsLevels({ ...all, platform: [] });
    expect(currentSettingsLevel(levels, '/settings/users')).toBeNull();
  });
});

describe('the tabs of Settings', () => {
  const nothingVisited = () => null;

  it('are none with one level', () => {
    expect(settingsTabs(settingsLevels(member), '/account/profile', { mobile: false, lastVisited: nothingVisited })).toEqual([]);
  });

  it('are the levels, widest first, the page\'s marked and staying on the page', () => {
    const tabs = settingsTabs(settingsLevels(all), '/settings/system/jobs', { mobile: false, lastVisited: nothingVisited });
    expect(tabs.map((tab) => [tab.label, tab.href, tab.active])).toEqual([
      ['Platform', '/settings/system/jobs', true],
      ['Organization', '/organizations/acme/settings/general', false],
      ['Workspace', '/workspace/ws-1/settings/general', false],
      ['Account', '/account/profile', false],
    ]);
  });

  it('open a level where the caller left it, while that is still one of its pages', () => {
    const visited: Record<string, string> = {
      workspace: '/workspace/ws-1/settings/agents/a-1',
      account: '/account',
      organization: '/organizations/gone/settings/members',
    };
    const tabs = settingsTabs(settingsLevels(all), '/settings/general', {
      mobile: false,
      lastVisited: (level) => visited[level] ?? null,
    });
    expect(Object.fromEntries(tabs.map((tab) => [tab.id, tab.href]))).toMatchObject({
      workspace: '/workspace/ws-1/settings/agents/a-1',
      account: '/account/profile',
      organization: '/organizations/acme/settings/general',
    });
  });

  it('open a level\'s list on a phone', () => {
    const tabs = settingsTabs(settingsLevels(all), '/settings', {
      mobile: true,
      lastVisited: () => '/workspace/ws-1/settings/agents',
    });
    expect(tabs.map((tab) => tab.href)).toEqual(['/settings', '/organizations/acme/settings', '/workspace/ws-1/settings', '/account']);
  });
});
