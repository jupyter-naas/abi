// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { buildSettingsScopeMenuEntries, opensAnotherPage } from './settings-scope-list';

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

  it('never lists the workspace: settings scopes only, narrowest first', () => {
    const entries = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'platform' },
      showPlatform: true,
      platformActions: platformAdmin,
      organizations: [{ id: 'acme', name: 'Acme' }],
    });
    expect(entries.map((e) => e.id)).toEqual(['account', 'org:acme', 'platform']);
  });

  it('names the scopes by what they are, the organization included when it is the only one', () => {
    const entries = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'account' },
      showPlatform: true,
      platformActions: platformAdmin,
      organizations: [{ id: 'acme', name: 'JOE Platform' }],
    });
    expect(entries.map((e) => (e.type === 'item' ? e.label : '—'))).toEqual([
      'Account',
      'Organization',
      'Platform',
    ]);
  });

  it('sets several organizations apart, by name', () => {
    const entries = buildSettingsScopeMenuEntries({
      currentScope: { kind: 'account' },
      showPlatform: true,
      platformActions: platformAdmin,
      organizations: [
        { id: 'alpha', name: 'Alpha Co' },
        { id: 'beta', name: 'Beta Co' },
      ],
    });
    expect(entries.map((e) => (e.type === 'item' ? e.label : '—'))).toEqual([
      'Account',
      '—',
      'Organization · Alpha Co',
      'Organization · Beta Co',
      '—',
      'Platform',
    ]);
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

});

describe('opensAnotherPage', () => {
  it('is true for another path, ignoring query and hash', () => {
    expect(opensAnotherPage('/organizations/org-1/settings', '/settings/general')).toBe(true);
    expect(opensAnotherPage('/account/profile?tab=a#b', '/account/security')).toBe(true);
  });

  it('is false for the page already open: no navigation, so nothing pending', () => {
    expect(opensAnotherPage('/settings/general', '/settings/general')).toBe(false);
    expect(opensAnotherPage('/settings/general?x=1#y', '/settings/general')).toBe(false);
  });

  it('is false without a current path', () => {
    expect(opensAnotherPage('/settings/general', null)).toBe(false);
  });
});
