import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.hoisted(() => vi.fn());
vi.mock('@/stores/auth', () => ({ authFetch }));
vi.mock('@/lib/config', () => ({ getApiUrl: () => 'https://api.test' }));

import { topicsApi } from './search-topics-api';
import { SEARCH_SOURCE_IDS } from './search-scopes';

const json = (status: number, body: unknown) =>
  ({ ok: status < 400, status, json: async () => body }) as Response;

describe('a search source is switched in the workspace’s offer', () => {
  beforeEach(() => authFetch.mockReset());

  it('writes the source into the offer and answers what it leaves out', async () => {
    const offered = SEARCH_SOURCE_IDS.filter((id) => id !== 'web.duckduckgo');
    authFetch.mockResolvedValue(json(200, { offered: { search_sources: offered } }));
    const { disabled_scopes } = await topicsApi.setScopeEnabled('ws-1', 'web.duckduckgo', false);
    const [url, init] = authFetch.mock.calls[0];
    expect(url).toBe('https://api.test/api/workspaces/ws-1/offer/search-sources');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body)).toEqual({ changes: { 'web.duckduckgo': false } });
    expect(disabled_scopes).toEqual(['web.duckduckgo']);
  });

  it('says why IAM refused', async () => {
    authFetch.mockResolvedValue(json(422, { detail: 'It would grant nothing beyond the organization' }));
    await expect(topicsApi.setScopeEnabled('ws-1', 'maps', true)).rejects.toThrow('would grant nothing');
  });
});
