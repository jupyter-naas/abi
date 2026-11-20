import { describe, expect, it } from 'vitest';
import { accountSettingsNavVisible } from '@/app/account/lib/nav';
import { orgSettingsNavForRole } from '@/app/organizations/[orgId]/settings/lib/nav';
import { visibleAdministrationItems } from '@/app/settings/lib/nav';
import { SETTINGS_GROUPS } from '@/components/shell/settings-nav';
import { activeSettingsHref, settingsLevels, type SettingsLevelsInput } from './settings-levels';

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

describe('the levels of Settings', () => {
  it('shows a member their account alone', () => {
    expect(titles(member)).toEqual(['Account']);
  });

  it('goes from the narrowest level to the widest, each with only what the caller opens', () => {
    const all: SettingsLevelsInput = {
      ...member,
      workspace: { id: 'ws-1', groups: SETTINGS_GROUPS },
      organization: { id: 'acme', name: 'Acme', items: orgSettingsNavForRole('admin', { holdsIam: true }), current: true },
      platform: visibleAdministrationItems({ 'nexus:ReadSystem': true, 'nexus:ListUsers': true }),
    };
    expect(titles(all)).toEqual(['Account', 'Workspace', 'Organization', 'Platform']);
    expect(labels(all, 'organization')).toContain('Members');
    expect(labels(all, 'platform')).toEqual(['General', 'Organizations', 'Users']);
  });

  it('roots the workspace pages at the workspace, its later groups named under the level', () => {
    const [, workspace] = settingsLevels({ ...member, workspace: { id: 'ws-1', groups: SETTINGS_GROUPS } });
    expect(workspace.groups.map((group) => group.label)).toEqual([null, 'Features']);
    expect(workspace.groups[0].links[0].href).toBe('/workspace/ws-1/settings/general');
  });

  it('leaves a level out when the caller opens nothing there', () => {
    const input: SettingsLevelsInput = {
      ...member,
      workspace: { id: 'ws-1', groups: [{ label: 'General', items: [] }] },
      organization: { id: 'acme', name: 'Acme', items: [], current: true },
    };
    expect(titles(input)).toEqual(['Account']);
  });

  it('names the organization when the caller opens several, and links the others', () => {
    const input: SettingsLevelsInput = {
      ...member,
      organization: { id: 'acme', name: 'Acme', items: orgSettingsNavForRole('admin', { holdsIam: false }), current: true },
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
    const items = orgSettingsNavForRole('admin', { holdsIam: false });
    const elsewhere = { ...member, organization: { id: 'acme', name: 'Acme', items, current: false } };
    const here = { ...member, organization: { id: 'acme', name: 'Acme', items, current: true } };
    expect(titles(elsewhere)).toEqual(['Account', 'Organization · Acme']);
    expect(titles(here)).toEqual(['Account', 'Organization']);
  });

  it('lists the organizations when none is the page\'s or the workspace\'s', () => {
    const input = { ...member, otherOrganizations: [{ id: 'acme', name: 'Acme' }, { id: 'beta', name: 'Beta' }] };
    expect(titles(input)).toEqual(['Account', 'Organizations']);
  });

  it('marks the link a page is, or is under, the longest first', () => {
    const levels = settingsLevels({ ...member, workspace: { id: 'ws-1', groups: SETTINGS_GROUPS } });
    expect(activeSettingsHref(levels, '/workspace/ws-1/settings/agents/a-1')).toBe('/workspace/ws-1/settings/agents');
    expect(activeSettingsHref(levels, '/account/profile?tab=x')).toBe('/account/profile');
    expect(activeSettingsHref(levels, '/workspace/ws-1/chat')).toBeNull();
  });
});
