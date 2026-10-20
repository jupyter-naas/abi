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

  it('fetches again on a forced load while an older request is in flight', async () => {
    const resolvers: Array<(value: unknown) => void> = [];
    const get = vi.spyOn(mapsCatalogApi, 'get').mockImplementation(
      () => new Promise((r) => resolvers.push(r)) as ReturnType<typeof mapsCatalogApi.get>,
    );
    const { loadLayouts } = useMapsStore.getState();
    const first = loadLayouts('ws-1');
    const forced = loadLayouts('ws-1', true);
    expect(get).toHaveBeenCalledTimes(1);
    resolvers[0]({ layouts: [], feed_layers: [] });
    await first;
    // The change landed after the first request left: its answer is not the forced load's.
    await vi.waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    resolvers[1]({ layouts: [], feed_layers: [], hidden_layouts: ['a'] });
    await forced;
    expect(useMapsStore.getState().byWorkspace['ws-1'].hidden).toEqual(['a']);
  });
});
