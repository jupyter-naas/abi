import { describe, expect, it, vi } from 'vitest';
import {
  fetchWithSettingsCacheFallback,
  isSettingsRoute,
  resetSettingsCacheSupport,
  settingsCacheSupported,
  shouldUseSettingsCache,
} from './settings-cache';

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

describe('fetchWithSettingsCacheFallback', () => {
  it('retries once without the cache header when the request fails at the network level', async () => {
    resetSettingsCacheSupport();
    const calls: boolean[] = [];
    const send = vi.fn(async (useCache: boolean) => {
      calls.push(useCache);
      if (useCache) throw new TypeError('Failed to fetch');
      return new Response('{}');
    });
    const response = await fetchWithSettingsCacheFallback(true, send);
    expect(response.ok).toBe(true);
    expect(calls).toEqual([true, false]);
    // The API does not accept the header: stop sending it for this session.
    expect(settingsCacheSupported()).toBe(false);
  });

  it('sends the header when supported and wanted', async () => {
    resetSettingsCacheSupport();
    const send = vi.fn(async () => new Response('{}'));
    await fetchWithSettingsCacheFallback(true, send);
    expect(send).toHaveBeenCalledWith(true);
    expect(settingsCacheSupported()).toBe(true);
  });

  it('does not retry requests that never used the header', async () => {
    resetSettingsCacheSupport();
    const send = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    await expect(fetchWithSettingsCacheFallback(false, send)).rejects.toThrow('Failed to fetch');
    expect(send).toHaveBeenCalledTimes(1);
  });
});
