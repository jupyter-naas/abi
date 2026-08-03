import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('getApiUrl public-origin fallback', () => {
  const originalWindow = globalThis.window;
  const envKeys = [
    'NEXUS_API_URL',
    'NEXT_PUBLIC_API_URL',
    'NEXUS_ENV',
    'NEXT_PUBLIC_NEXUS_ENV',
  ] as const;
  const originalEnv: Partial<Record<(typeof envKeys)[number], string | undefined>> = {};

  beforeEach(() => {
    vi.resetModules();
    for (const key of envKeys) {
      originalEnv[key] = process.env[key];
      delete process.env[key];
    }
    delete (globalThis as { __NEXUS_RUNTIME_CONFIG__?: unknown }).__NEXUS_RUNTIME_CONFIG__;
  });

  afterEach(() => {
    for (const key of envKeys) {
      if (originalEnv[key] === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = originalEnv[key];
      }
    }
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: originalWindow,
    });
    delete (globalThis as { __NEXUS_RUNTIME_CONFIG__?: unknown }).__NEXUS_RUNTIME_CONFIG__;
    vi.restoreAllMocks();
  });

  it('refuses localhost when the page origin is public and config is missing', async () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        location: {
          hostname: 'app.example.com',
          origin: 'https://app.example.com',
          protocol: 'https:',
        },
        __NEXUS_RUNTIME_CONFIG__: undefined,
      },
    });
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const { getApiUrl, getEnvironment } = await import('./config');

    expect(getEnvironment()).toBe('cloudflare');
    expect(getApiUrl()).toBe('https://api.app.example.com');
    expect(warn).toHaveBeenCalled();
  });

  it('prefers runtime-config apiUrl when present', async () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        location: {
          hostname: 'app.example.com',
          origin: 'https://app.example.com',
          protocol: 'https:',
        },
        __NEXUS_RUNTIME_CONFIG__: {
          apiUrl: 'https://api.app.example.com',
          env: 'cloudflare',
        },
      },
    });

    const { getApiUrl } = await import('./config');
    expect(getApiUrl()).toBe('https://api.app.example.com');
  });

  it('keeps localhost defaults for local browser origins', async () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        location: {
          hostname: 'localhost',
          origin: 'http://localhost:3000',
          protocol: 'http:',
        },
        __NEXUS_RUNTIME_CONFIG__: undefined,
      },
    });

    const { getApiUrl, getEnvironment } = await import('./config');
    expect(getEnvironment()).toBe('local');
    expect(getApiUrl()).toBe('http://localhost:9879');
  });
});
