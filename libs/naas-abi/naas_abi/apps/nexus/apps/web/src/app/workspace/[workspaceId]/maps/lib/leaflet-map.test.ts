import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { observeMapsLeafletSize } from './leaflet-map';

describe('observeMapsLeafletSize', () => {
  const observers: ResizeObserverCallback[] = [];
  let observe: ReturnType<typeof vi.fn>;
  let disconnect: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    observers.length = 0;
    observe = vi.fn();
    disconnect = vi.fn();
    vi.stubGlobal('window', {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      setTimeout: (cb: () => void, ms?: number) =>
        globalThis.setTimeout(cb, ms) as unknown as number,
      clearTimeout: (id: number) => globalThis.clearTimeout(id),
    });
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(cb: ResizeObserverCallback) {
          observers.push(cb);
        }
        observe = observe;
        disconnect = disconnect;
        unobserve = vi.fn();
      },
    );
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      cb(0);
      return 1;
    });
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('invalidates on observe, resize, and after panel transition', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const invalidateSize = vi.fn();
    const once = vi.fn();
    const container = {} as HTMLElement;
    const map = {
      getContainer: () => container,
      invalidateSize,
      once,
    };

    const stop = observeMapsLeafletSize(map as never);

    expect(observe).toHaveBeenCalledTimes(1);
    expect(invalidateSize).toHaveBeenCalledWith({ animate: false });

    invalidateSize.mockClear();
    observers[0]?.([], {} as ResizeObserver);
    expect(invalidateSize).toHaveBeenCalledWith({ animate: false });

    invalidateSize.mockClear();
    vi.advanceTimersByTime(320);
    expect(invalidateSize).toHaveBeenCalledWith({ animate: false });

    stop();
    expect(disconnect).toHaveBeenCalledTimes(1);
    expect(once).toHaveBeenCalledWith('unload', expect.any(Function));
  });
});
