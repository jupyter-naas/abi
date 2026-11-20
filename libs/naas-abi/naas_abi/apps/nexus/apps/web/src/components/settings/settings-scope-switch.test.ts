import { describe, expect, it } from 'vitest';
import {
  organizationSettingsSwitchPath,
  organizationsOfWorkspaces,
  settingsOrganizationId,
  settingsWorkspaceId,
  workspaceSettingsSwitchPath,
} from './settings-scope-switch';

describe('the Settings column switchers', () => {
  it('reads the level of the page', () => {
    expect(settingsWorkspaceId('/workspace/ws-1/settings/users/usr_1')).toBe('ws-1');
    expect(settingsWorkspaceId('/org/acme/workspace/ws-1/settings')).toBe('ws-1');
    expect(settingsWorkspaceId('/workspace/ws-1/home')).toBeNull();
    expect(settingsOrganizationId('/organizations/org-1/settings/workspaces')).toBe('org-1');
    expect(settingsOrganizationId('/settings/users')).toBeNull();
  });

  it('keeps the section, leaves a row of the level left behind', () => {
    expect(workspaceSettingsSwitchPath('/workspace/ws-1/settings/users/usr_1', 'ws-2')).toBe('/workspace/ws-2/settings/users');
    expect(workspaceSettingsSwitchPath('/org/acme/workspace/ws-1/settings/analytics?days=7', 'ws-2')).toBe(
      '/workspace/ws-2/settings/analytics'
    );
    expect(workspaceSettingsSwitchPath('/workspace/ws-1/settings', 'ws-2')).toBe('/workspace/ws-2/settings');
    expect(organizationSettingsSwitchPath('/organizations/org-1/settings/groups/grp_1', 'org-2')).toBe(
      '/organizations/org-2/settings/groups'
    );
  });

  it('lists the organizations of the workspaces, by name, each with its workspaces by name', () => {
    const orgs = organizationsOfWorkspaces([
      { id: 'w3', name: 'Zeta', organizationId: 'b', organizationName: 'Beta' },
      { id: 'w1', name: 'Ops', organizationId: 'a', organizationName: 'Acme' },
      { id: 'w2', name: 'Lab', organizationId: 'a', organizationName: 'Acme' },
      { id: 'w4', name: 'Solo' },
    ]);
    expect(orgs.map((o) => o.name)).toEqual(['Acme', 'Beta']);
    expect(orgs[0].workspaces.map((w) => w.name)).toEqual(['Lab', 'Ops']);
  });
});
