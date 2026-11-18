// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { buildSettingsScopeMenuEntries } from './settings-scope-list';

const platformAdmin = { 'nexus:ListOrganizations': true, 'iam:ListPolicies': true };

describe('buildSettingsScopeMenuEntries', () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it('lists platform only when showPlatform is true', () => {
    const withPlatform = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'account' },
      showPlatform: true,
      platformActions: platformAdmin,
      organizations: [],
      workspace: null,
    });
    expect(withPlatform.some((e) => e.type === 'item' && e.id === 'platform')).toBe(true);

    const without = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'account' },
      showPlatform: false,
      platformActions: null,
      organizations: [],
      workspace: null,
    });
    expect(without.some((e) => e.type === 'item' && e.id === 'platform')).toBe(false);
  });

  it('lists openable organizations by name and marks current org', () => {
    const entries = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'organization', orgId: 'beta' },
      showPlatform: false,
      platformActions: null,
      organizations: [
        { id: 'alpha', name: 'Alpha Co' },
        { id: 'beta', name: 'Beta Co' },
      ],
      workspace: null,
    });
    expect(entries.some((e) => e.type === 'separator' && e.id === 'orgs-sep')).toBe(true);
    const beta = entries.find((e) => e.type === 'item' && e.id === 'org:beta');
    expect(beta).toMatchObject({ type: 'item', label: 'Beta Co', current: true });
    const alpha = entries.find((e) => e.type === 'item' && e.id === 'org:alpha');
    expect(alpha).toMatchObject({ current: false, href: '/organizations/alpha/settings' });
  });

  it('adds workspace as an external link when given', () => {
    const entries = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'platform' },
      showPlatform: true,
      platformActions: platformAdmin,
      organizations: [],
      workspace: { id: 'ws-1', name: 'Bob' },
    });
    const ws = entries.find((e) => e.type === 'item' && e.id === 'workspace');
    expect(ws).toMatchObject({
      label: 'Workspace · Bob',
      href: '/workspace/ws-1/settings',
      external: true,
    });
  });

  it('reuses remembered paths when switching', () => {
    sessionStorage.setItem('nexus-settings-scope-path:platform', '/settings/roles');
    const entries = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'account' },
      showPlatform: true,
      platformActions: platformAdmin,
      organizations: [],
      workspace: null,
    });
    const platform = entries.find((e) => e.type === 'item' && e.id === 'platform');
    expect(platform).toMatchObject({ href: '/settings/roles' });
  });
});