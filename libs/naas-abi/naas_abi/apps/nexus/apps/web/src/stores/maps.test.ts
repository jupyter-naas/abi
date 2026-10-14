import { afterEach, describe, expect, it, vi } from 'vitest';

import { mapsCatalogApi } from '@/app/workspace/[workspaceId]/maps/lib/basemaps-api';
import { useMapsStore } from './maps';

afterEach(() => {
  vi.restoreAllMocks();
  useMapsStore.setState({ byWorkspace: {}, loading: false, error: null });
});

describe('loadLayouts', () => {
  it('shares one catalog request between the components that ask at once', async () => {
    let resolve!: (value: unknown) => void;
    const get = vi
      .spyOn(mapsCatalogApi, 'get')
      .mockReturnValue(new Promise((r) => (resolve = r)) as ReturnType<typeof mapsCatalogApi.get>);
    const { loadLayouts } = useMapsStore.getState();
    const loads = [loadLayouts('ws-1'), loadLayouts('ws-1'), loadLayouts('ws-1')];
    resolve({ layouts: [], feed_layers: [] });
    await Promise.all(loads);
    expect(get).toHaveBeenCalledTimes(1);
    // Loaded: later calls do not ask again; `force` does.
    await loadLayouts('ws-1');
    expect(get).toHaveBeenCalledTimes(1);
  });
});
