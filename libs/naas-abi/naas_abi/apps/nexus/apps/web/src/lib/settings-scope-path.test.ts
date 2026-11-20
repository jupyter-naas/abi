// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import {
  forgetSettingsPaths,
  isWorkspaceSettingsPath,
  rememberSettingsPath,
  settingsReturnPath,
  settingsScopeFromPathname,
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
    expect(isWorkspaceSettingsPath('/workspace/ws-1/settings/general')).toBe(true);
    expect(isWorkspaceSettingsPath('/workspace/ws-1/chat')).toBe(false);
  });
});

describe('the last Settings and Console pages', () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it('reopens the last Settings page, whatever its level', () => {
    rememberSettingsPath('settings', '/account/appearance');
    rememberSettingsPath('settings', '/organizations/acme/settings/users');
    expect(settingsReturnPath('settings', '/account/profile')).toBe('/organizations/acme/settings/users');
  });

  it('keeps the Console apart', () => {
    rememberSettingsPath('settings', '/workspace/ws-1/settings/agents');
    rememberSettingsPath('console', '/settings/system/jobs');
    expect(settingsReturnPath('settings', '/account/profile')).toBe('/workspace/ws-1/settings/agents');
    expect(settingsReturnPath('console', '/settings/system')).toBe('/settings/system/jobs');
  });

  it('falls back when nothing was visited, or the stored path is not a settings page', () => {
    expect(settingsReturnPath('settings', '/account/profile')).toBe('/account/profile');
    rememberSettingsPath('settings', '/workspace/ws-1/chat');
    rememberSettingsPath('settings', '//evil.example/account');
    expect(settingsReturnPath('settings', '/account/profile')).toBe('/account/profile');
  });

  it('forgets both at sign-out, so the next person starts from their own landing', () => {
    rememberSettingsPath('settings', '/organizations/acme/settings/users');
    rememberSettingsPath('console', '/settings/system/jobs');
    forgetSettingsPaths();
    expect(settingsReturnPath('settings', '/account/profile')).toBe('/account/profile');
    expect(settingsReturnPath('console', '/settings/system')).toBe('/settings/system');
  });
});
