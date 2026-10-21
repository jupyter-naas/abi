import { afterEach, describe, expect, it, vi } from 'vitest';

import { clearSharedFeedLoads, sharedFeedLoad } from './shared-feed-loads';

const COLLECTION = {
  type: 'FeatureCollection',
  features: [{ type: 'Feature', id: 'a', geometry: { type: 'Point', coordinates: [2, 48] }, properties: { label: 'A' } }],
};

function mockFetch(responses: Array<() => Response>) {
  const fetchMock = vi.fn(async () => responses.shift()!());
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  clearSharedFeedLoads();
  vi.unstubAllGlobals();
});

describe('sharedFeedLoad', () => {
  it('shares one request between callers (map, sidebar counts, remounts)', async () => {
    const fetchMock = mockFetch([() => new Response(JSON.stringify(COLLECTION))]);
    const [a, b] = await Promise.all([sharedFeedLoad('/data/x'), sharedFeedLoad('/data/x')]);
    expect(a.pins).toHaveLength(1);
    expect(b).toBe(a);
    await sharedFeedLoad('/data/x');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('layers sharing one object share its load', async () => {
    const fetchMock = mockFetch([() => new Response(JSON.stringify(COLLECTION))]);
    await sharedFeedLoad('/layers/a/data', undefined, undefined, 'ws-1:maps/x.geojson');
    await sharedFeedLoad('/layers/b/data', undefined, undefined, 'ws-1:maps/x.geojson');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not keep failures', async () => {
    const fetchMock = mockFetch([
      () => new Response(JSON.stringify({ detail: 'busy' }), { status: 503 }),
      () => new Response(JSON.stringify(COLLECTION)),
    ]);
    await expect(sharedFeedLoad('/data/y')).rejects.toThrow();
    expect((await sharedFeedLoad('/data/y')).pins).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("one caller's abort leaves the shared request to the others", async () => {
    mockFetch([() => new Response(JSON.stringify(COLLECTION))]);
    const controller = new AbortController();
    const aborted = sharedFeedLoad('/data/z', undefined, controller.signal);
    const kept = sharedFeedLoad('/data/z');
    controller.abort();
    await expect(aborted).rejects.toThrow();
    expect((await kept).pins).toHaveLength(1);
  });
});
