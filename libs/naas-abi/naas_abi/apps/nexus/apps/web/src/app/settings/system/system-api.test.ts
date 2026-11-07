import { describe, expect, it, vi } from 'vitest';

vi.mock('@/stores/auth', () => ({ authFetch: vi.fn() }));

import { loadSystem } from './system-api';

function response(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('loadSystem', () => {
  it('returns the data of a successful call', async () => {
    const fetcher = vi.fn().mockResolvedValue(response(200, { kernel_services: 3 }));

    const loaded = await loadSystem('/overview', fetcher);

    expect(fetcher).toHaveBeenCalledWith('/api/admin/system/overview');
    expect(loaded).toEqual({ ok: true, data: { kernel_services: 3 } });
  });

  it('names the missing source of a 503', async () => {
    const fetcher = vi.fn().mockResolvedValue(
      response(503, { detail: { source: 'nats_monitor', reason: 'connection refused' } }),
    );

    expect(await loadSystem('/nats/server', fetcher)).toEqual({
      ok: false,
      status: 503,
      source: 'nats_monitor',
      reason: 'connection refused',
    });
  });

  it('explains a 403 and network failures', async () => {
    const forbidden = vi.fn().mockResolvedValue(response(403, { detail: 'Platform superadmin role required' }));
    expect(await loadSystem('/services', forbidden)).toMatchObject({
      ok: false,
      status: 403,
      reason: 'Platform superadmin role required',
    });

    const offline = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    expect(await loadSystem('/services', offline)).toEqual({ ok: false, status: 0, reason: 'Failed to fetch' });
  });
});
