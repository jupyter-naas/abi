// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import {
  forgetSettingsPaths,
  isWorkspaceSettingsPath,
  rememberSettingsPath,
  settingsLevelReturnPath,
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

describe('the last Settings pages', () => {
  afterEach(() => {
    sessionStorage.clear();
  });

  it('reopens the last Settings page, whatever its level', () => {
    rememberSettingsPath('/account/appearance');
    rememberSettingsPath('/organizations/acme/settings/users');
    expect(settingsReturnPath('/account/profile')).toBe('/organizations/acme/settings/users');
  });

  it('keeps the last page of each level, for its tab', () => {
    rememberSettingsPath('/settings/system/jobs');
    rememberSettingsPath('/workspace/ws-1/settings/agents');
    rememberSettingsPath('/account/appearance');
    expect(settingsLevelReturnPath('platform')).toBe('/settings/system/jobs');
    expect(settingsLevelReturnPath('workspace')).toBe('/workspace/ws-1/settings/agents');
    expect(settingsLevelReturnPath('account')).toBe('/account/appearance');
    expect(settingsLevelReturnPath('organization')).toBeNull();
  });

  it('falls back when nothing was visited, or the stored path is not a settings page', () => {
    expect(settingsReturnPath('/account/profile')).toBe('/account/profile');
    rememberSettingsPath('/workspace/ws-1/chat');
    rememberSettingsPath('//evil.example/account');
    expect(settingsReturnPath('/account/profile')).toBe('/account/profile');
    sessionStorage.setItem('nexus-settings-return-path:level:platform', '/workspace/ws-1/settings/general');
    expect(settingsLevelReturnPath('platform')).toBeNull();
  });

  it('forgets them all at sign-out, the Console\'s old one too, so the next person starts from their own landing', () => {
    rememberSettingsPath('/organizations/acme/settings/users');
    rememberSettingsPath('/settings/users');
    sessionStorage.setItem('nexus-settings-return-path:console', '/settings/system/jobs');
    forgetSettingsPaths();
    expect(settingsReturnPath('/account/profile')).toBe('/account/profile');
    expect(settingsLevelReturnPath('organization')).toBeNull();
    expect(settingsLevelReturnPath('platform')).toBeNull();
    expect(sessionStorage.length).toBe(0);
  });
});
