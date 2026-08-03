import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

import { getSafeStorage, resetSafeStorageForTests } from './safe-storage';

describe('getSafeStorage', () => {
  const originalWindow = globalThis.window;
  const originalLocal = globalThis.localStorage;
  const originalSession = globalThis.sessionStorage;

  beforeEach(() => {
    resetSafeStorageForTests();
  });

  afterEach(() => {
    resetSafeStorageForTests();
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: originalWindow,
    });
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: originalLocal,
    });
    Object.defineProperty(globalThis, 'sessionStorage', {
      configurable: true,
      value: originalSession,
    });
  });

  it('falls back to memory when browser storage throws', () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: globalThis,
    });
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        setItem: () => {
          throw new DOMException('blocked', 'QuotaExceededError');
        },
        getItem: () => null,
        removeItem: () => undefined,
      },
    });
    Object.defineProperty(globalThis, 'sessionStorage', {
      configurable: true,
      value: {
        setItem: () => {
          throw new DOMException('blocked', 'QuotaExceededError');
        },
        getItem: () => null,
        removeItem: () => undefined,
      },
    });

    const storage = getSafeStorage();
    expect(storage.backend).toBe('memory');
    storage.setItem('nexus-auth', '{"token":"abc"}');
    expect(storage.getItem('nexus-auth')).toBe('{"token":"abc"}');
    storage.removeItem('nexus-auth');
    expect(storage.getItem('nexus-auth')).toBeNull();
  });

  it('prefers sessionStorage when localStorage is blocked', () => {
    const sessionBacking = new Map<string, string>();

    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: globalThis,
    });
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        setItem: () => {
          throw new DOMException('blocked', 'QuotaExceededError');
        },
        getItem: () => null,
        removeItem: () => undefined,
      },
    });
    Object.defineProperty(globalThis, 'sessionStorage', {
      configurable: true,
      value: {
        setItem: (key: string, value: string) => {
          sessionBacking.set(key, value);
        },
        getItem: (key: string) => sessionBacking.get(key) ?? null,
        removeItem: (key: string) => {
          sessionBacking.delete(key);
        },
      },
    });

    const storage = getSafeStorage();
    expect(storage.backend).toBe('sessionStorage');
    storage.setItem('nexus-auth', '{"token":"session"}');
    expect(storage.getItem('nexus-auth')).toBe('{"token":"session"}');
  });
});
