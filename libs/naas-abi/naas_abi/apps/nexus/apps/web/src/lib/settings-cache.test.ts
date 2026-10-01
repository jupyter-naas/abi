import { describe, expect, it } from 'vitest';
import { isSettingsRoute, shouldUseSettingsCache } from './settings-cache';

describe('isSettingsRoute', () => {
  it('matches workspace and organization settings pages', () => {
    expect(isSettingsRoute('/workspace/ws-1/settings')).toBe(true);
    expect(isSettingsRoute('/workspace/ws-1/settings/agents/a1')).toBe(true);
    expect(isSettingsRoute('/organizations/org-1/settings/users')).toBe(true);
  });

  it('ignores every other page', () => {
    expect(isSettingsRoute('/workspace/ws-1/chat')).toBe(false);
    expect(isSettingsRoute('/workspace/ws-1/settingsx')).toBe(false);
    expect(isSettingsRoute('/account/settings')).toBe(false);
  });
});

describe('shouldUseSettingsCache', () => {
  it('opts in GET requests from settings pages only', () => {
    expect(shouldUseSettingsCache('/workspace/ws-1/settings/agents', undefined)).toBe(true);
    expect(shouldUseSettingsCache('/workspace/ws-1/settings/agents', 'get')).toBe(true);
    expect(shouldUseSettingsCache('/workspace/ws-1/settings/agents', 'PATCH')).toBe(false);
    expect(shouldUseSettingsCache('/workspace/ws-1/chat', 'GET')).toBe(false);
  });
});
