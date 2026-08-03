import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  canInvalidateMapsLeaflet,
  observeMapsLeafletSize,
  safeInvalidateMapsLeafletSize,
} from './leaflet-map';

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

  it('does not invalidate after stop even if delayed callbacks fire', () => {
    const rafCallbacks: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      rafCallbacks.push(cb);
      return rafCallbacks.length;
    });
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });

    const invalidateSize = vi.fn();
    const map = {
      getContainer: () => ({ isConnected: true }) as HTMLElement,
      invalidateSize,
      once: vi.fn(),
      _mapPane: { isConnected: true },
    };

    const stop = observeMapsLeafletSize(map as never);
    expect(rafCallbacks).toHaveLength(1);

    stop();
    rafCallbacks[0]?.(0);
    vi.advanceTimersByTime(320);

    expect(invalidateSize).not.toHaveBeenCalled();
    expect(disconnect).toHaveBeenCalledTimes(1);
  });
});

describe('canInvalidateMapsLeaflet / safeInvalidateMapsLeafletSize', () => {
  it('rejects detached containers and missing map panes', () => {
    expect(canInvalidateMapsLeaflet(null)).toBe(false);
    expect(
      canInvalidateMapsLeaflet({
        getContainer: () => ({ isConnected: false }) as HTMLElement,
        invalidateSize: vi.fn(),
      } as never),
    ).toBe(false);
    expect(
      canInvalidateMapsLeaflet({
        getContainer: () => ({ isConnected: true }) as HTMLElement,
        invalidateSize: vi.fn(),
        _mapPane: null,
      } as never),
    ).toBe(false);
  });

  it('swallows invalidateSize errors from torn-down Leaflet maps', () => {
    const map = {
      getContainer: () => ({ isConnected: true }) as HTMLElement,
      invalidateSize: vi.fn(() => {
        throw new TypeError(
          "Cannot read properties of undefined (reading '_leaflet_pos')",
        );
      }),
      _mapPane: { isConnected: true },
    };
    expect(() => safeInvalidateMapsLeafletSize(map as never)).not.toThrow();
  });
});
