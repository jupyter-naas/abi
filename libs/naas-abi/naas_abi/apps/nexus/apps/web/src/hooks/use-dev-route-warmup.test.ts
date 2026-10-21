import { beforeEach, describe, expect, it, vi } from 'vitest';
import { resetWarmedRoutes, warmRoutes } from './use-dev-route-warmup';

describe('warmRoutes', () => {
  beforeEach(() => resetWarmedRoutes());

  it('requests each route once, in order, as an RSC fetch', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(''));
    await warmRoutes(['/a', '/b'], fetchImpl);
    expect(fetchImpl.mock.calls.map((c) => c[0])).toEqual(['/a', '/b']);
    expect(fetchImpl.mock.calls[0][1]).toMatchObject({ headers: { RSC: '1' } });
  });

  it('skips routes that were already warmed', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(''));
    await warmRoutes(['/a'], fetchImpl);
    await warmRoutes(['/a', '/b'], fetchImpl);
    expect(fetchImpl.mock.calls.map((c) => c[0])).toEqual(['/a', '/b']);
  });

  it('keeps going when one request fails', async () => {
    const fetchImpl = vi.fn().mockRejectedValueOnce(new Error('boom')).mockResolvedValue(new Response(''));
    await warmRoutes(['/a', '/b'], fetchImpl);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it('stops when cancelled', async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(''));
    let cancelled = false;
    fetchImpl.mockImplementationOnce(async () => {
      cancelled = true;
      return new Response('');
    });
    await warmRoutes(['/a', '/b'], fetchImpl, () => cancelled);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
