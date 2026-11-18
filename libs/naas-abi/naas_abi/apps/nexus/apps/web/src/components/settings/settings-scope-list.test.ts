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
    });
    expect(withPlatform.some((e) => e.type === 'item' && e.id === 'platform')).toBe(true);

    const without = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'account' },
      showPlatform: false,
      platformActions: null,
      organizations: [],
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
    });
    expect(entries.some((e) => e.type === 'separator' && e.id === 'orgs-sep')).toBe(true);
    const beta = entries.find((e) => e.type === 'item' && e.id === 'org:beta');
    expect(beta).toMatchObject({ type: 'item', label: 'Organization · Beta Co', current: true });
    const alpha = entries.find((e) => e.type === 'item' && e.id === 'org:alpha');
    expect(alpha).toMatchObject({ current: false, href: '/organizations/alpha/settings' });
  });

  it('never lists the workspace: settings scopes only', () => {
    const entries = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'platform' },
      showPlatform: true,
      platformActions: platformAdmin,
      organizations: [{ id: 'acme', name: 'Acme' }],
      accountName: 'Bob',
    });
    expect(entries.map((e) => e.id)).toEqual(['platform', 'account', 'orgs-sep', 'org:acme']);
  });

  it('reuses remembered paths when switching', () => {
    sessionStorage.setItem('nexus-settings-scope-path:platform', '/settings/roles');
    const entries = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'account' },
      showPlatform: true,
      platformActions: platformAdmin,
      organizations: [],
    });
    const platform = entries.find((e) => e.type === 'item' && e.id === 'platform');
    expect(platform).toMatchObject({ href: '/settings/roles' });
  });

  it("labels Account with the signed-in user's name", () => {
    const base = {
      currentScope: { kind: 'account' } as const,
      showPlatform: false,
      platformActions: null,
      organizations: [],
    };
    const named = buildSettingsScopeMenuEntries({ ...base, accountName: 'Olivia Martin' });
    expect(named.find((e) => e.type === 'item' && e.id === 'account')).toMatchObject({
      label: 'Olivia Martin',
      current: true,
    });
    const unnamed = buildSettingsScopeMenuEntries({ ...base, accountName: '  ' });
    expect(unnamed.find((e) => e.type === 'item' && e.id === 'account')).toMatchObject({ label: 'Account' });
  });
});
