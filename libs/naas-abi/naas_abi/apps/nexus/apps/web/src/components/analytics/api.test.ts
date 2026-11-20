import { describe, expect, it, vi } from 'vitest';
import { AnalyticsHttpError, NO_ANALYTICS_ACCESS, analyticsAccessFrom, fetchAnalyticsAccess, readAnalyticsJson } from './api';

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('GET {base}/analytics/access', () => {
  it('asks the scope\'s /access and reads its flags and timezone', async () => {
    const fetcher = vi.fn(async () =>
      json(200, { can_read: true, can_read_conversations: false, timezone: 'Europe/Paris' })
    );
    await expect(fetchAnalyticsAccess({ kind: 'organization', orgId: 'org-1' }, fetcher)).resolves.toEqual({
      can_read: true,
      can_read_conversations: false,
      timezone: 'Europe/Paris',
    });
    expect(fetcher).toHaveBeenCalledWith('/api/organizations/org-1/analytics/access');
  });

  it('reads 401, 403 and 404 as no access, and throws on any other failure', async () => {
    for (const status of [401, 403, 404]) {
      await expect(
        fetchAnalyticsAccess({ kind: 'workspace', workspaceId: 'ws-1' }, async () => json(status, {}))
      ).resolves.toEqual(NO_ANALYTICS_ACCESS);
    }
    await expect(
      fetchAnalyticsAccess({ kind: 'workspace', workspaceId: 'ws-1' }, async () => json(500, {}))
    ).rejects.toBeInstanceOf(AnalyticsHttpError);
  });

  it('makes a partial answer safe: missing flags false, missing timezone UTC', () => {
    expect(analyticsAccessFrom({ can_read: true })).toEqual({ can_read: true, can_read_conversations: false, timezone: 'UTC' });
    expect(analyticsAccessFrom(null)).toEqual(NO_ANALYTICS_ACCESS);
    expect(analyticsAccessFrom({ can_read: 'yes', timezone: '' })).toEqual(NO_ANALYTICS_ACCESS);
  });
});

describe('readAnalyticsJson', () => {
  it('returns the body of a success', async () => {
    await expect(readAnalyticsJson(json(200, { ok: 1 }))).resolves.toEqual({ ok: 1 });
  });

  it('throws the status and the API detail of a refusal', async () => {
    const error = await readAnalyticsJson(json(404, { detail: 'User not in scope' })).catch((e) => e);
    expect(error).toBeInstanceOf(AnalyticsHttpError);
    expect(error.status).toBe(404);
    expect(error.message).toBe('User not in scope (404)');
    const bare = await readAnalyticsJson(new Response('oops', { status: 403 })).catch((e) => e);
    expect(bare.status).toBe(403);
    expect(bare.message).toBe('Request failed (403)');
  });
});
