// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import {
  rememberSettingsScopePath,
  settingsScopeFromPathname,
  settingsScopeReturnPath,
  scopeKeysEqual,
} from './settings-scope-path';

describe('settingsScopeFromPathname', () => {
  it('detects account, platform and organization scopes', () => {
    expect(settingsScopeFromPathname('/account/profile')).toEqual({ kind: 'account' });
    expect(settingsScopeFromPathname('/settings/users')).toEqual({ kind: 'platform' });
    expect(settingsScopeFromPathname('/organizations/acme/settings/branding')).toEqual({
      kind: 'organization',
      orgId: 'acme',
    });
  });

  it('detects workspace settings', () => {
    expect(settingsScopeFromPathname('/workspace/ws-1/settings/general')).toEqual({
      kind: 'workspace',
      workspaceId: 'ws-1',
    });
  });
});

describe('rememberSettingsScopePath', () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it('remembers and restores per scope', () => {
    rememberSettingsScopePath({ kind: 'account' }, '/account/appearance');
    rememberSettingsScopePath({ kind: 'platform' }, '/settings/roles');
    rememberSettingsScopePath({ kind: 'organization', orgId: 'acme' }, '/organizations/acme/settings/users');

    expect(settingsScopeReturnPath({ kind: 'account' }, '/account/profile')).toBe('/account/appearance');
    expect(settingsScopeReturnPath({ kind: 'platform' }, '/settings')).toBe('/settings/roles');
    expect(settingsScopeReturnPath({ kind: 'organization', orgId: 'acme' }, '/organizations/acme/settings')).toBe(
      '/organizations/acme/settings/users'
    );
  });

  it('rejects paths outside the scope', () => {
    rememberSettingsScopePath({ kind: 'account' }, '/settings/users');
    expect(settingsScopeReturnPath({ kind: 'account' }, '/account/profile')).toBe('/account/profile');
  });

  it('keeps organization paths separate per org', () => {
    rememberSettingsScopePath({ kind: 'organization', orgId: 'a' }, '/organizations/a/settings/general');
    rememberSettingsScopePath({ kind: 'organization', orgId: 'b' }, '/organizations/b/settings/users');
    expect(settingsScopeReturnPath({ kind: 'organization', orgId: 'b' }, '/organizations/b/settings')).toBe(
      '/organizations/b/settings/users'
    );
  });
});

describe('scopeKeysEqual', () => {
  it('compares organization ids', () => {
    expect(
      scopeKeysEqual({ kind: 'organization', orgId: 'x' }, { kind: 'organization', orgId: 'x' })
    ).toBe(true);
    expect(
      scopeKeysEqual({ kind: 'organization', orgId: 'x' }, { kind: 'organization', orgId: 'y' })
    ).toBe(false);
  });
});