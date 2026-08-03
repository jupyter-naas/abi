import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  clearDevAutoLoginSuppression,
  isDevAutoLoginSuppressed,
  mergeAuthPersistedState,
  readDevAutoLoginConfig,
  shouldDevAutoLogin,
  shouldSkipMagicLinkConfirmation,
  suppressDevAutoLogin,
} from './auth-session';

describe('shouldSkipMagicLinkConfirmation', () => {
  it('confirms the token even when a stale session says the user is signed in', () => {
    // The regression: persisted isAuthenticated outlives its access token, so
    // redirecting here would discard the link the user just clicked.
    expect(shouldSkipMagicLinkConfirmation('fresh-token', true)).toBe(false);
  });

  it('confirms the token for a signed-out visitor', () => {
    expect(shouldSkipMagicLinkConfirmation('fresh-token', false)).toBe(false);
  });

  it('sends a signed-in visitor onward when the link carries no token', () => {
    expect(shouldSkipMagicLinkConfirmation(null, true)).toBe(true);
  });

  it('stays put for a signed-out visitor with no token so the error renders', () => {
    expect(shouldSkipMagicLinkConfirmation(null, false)).toBe(false);
  });
});

describe('mergeAuthPersistedState', () => {
  it('keeps live session when persisted storage is empty', () => {
    const current = {
      user: { id: '1', email: 'a@b.com', name: 'A', createdAt: new Date() },
      token: 'live-token',
      refreshToken: 'live-refresh',
      isAuthenticated: true,
      isLoading: false,
      error: null,
    };

    const merged = mergeAuthPersistedState(
      { user: null, token: null, refreshToken: null, isAuthenticated: false },
      current,
    );

    expect(merged.token).toBe('live-token');
    expect(merged.refreshToken).toBe('live-refresh');
    expect(merged.isAuthenticated).toBe(true);
  });

  it('applies persisted session when storage has tokens', () => {
    const current = {
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    };

    const merged = mergeAuthPersistedState(
      {
        user: { id: '2', email: 'c@d.com', name: 'C' },
        token: 'stored-token',
        refreshToken: 'stored-refresh',
        isAuthenticated: true,
      },
      current,
    );

    expect(merged.token).toBe('stored-token');
    expect(merged.refreshToken).toBe('stored-refresh');
    expect(merged.isAuthenticated).toBe(true);
  });
});

describe('shouldDevAutoLogin', () => {
  const credentials = { email: 'admin@example.com', password: 'generated-pw' };
  const base = {
    credentials,
    isAuthenticated: false,
    suppressed: false,
    optedOut: false,
    alreadyAttempted: false,
  };

  it('signs in when the server offered credentials and nothing objects', () => {
    expect(shouldDevAutoLogin(base)).toBe(true);
  });

  it('stays off when the server offered nothing (the production case)', () => {
    expect(shouldDevAutoLogin({ ...base, credentials: null })).toBe(false);
  });

  it('stays off when the server offered half a pair', () => {
    expect(
      shouldDevAutoLogin({ ...base, credentials: { email: 'a@b.com', password: '' } }),
    ).toBe(false);
  });

  it('does not re-sign-in a user who signed out', () => {
    // The regression this guards: "Sign out" that bounces you straight back in.
    expect(shouldDevAutoLogin({ ...base, suppressed: true })).toBe(false);
  });

  it('respects ?nologin=1 so the login page itself stays workable', () => {
    expect(shouldDevAutoLogin({ ...base, optedOut: true })).toBe(false);
  });

  it('leaves an already-signed-in user alone', () => {
    expect(shouldDevAutoLogin({ ...base, isAuthenticated: true })).toBe(false);
  });

  it('does not retry after an attempt, so a bad password surfaces its error', () => {
    expect(shouldDevAutoLogin({ ...base, alreadyAttempted: true })).toBe(false);
  });
});

describe('readDevAutoLoginConfig', () => {
  it('reads a complete pair', () => {
    expect(
      readDevAutoLoginConfig({
        password_auth_enabled: true,
        dev_autologin_email: 'admin@example.com',
        dev_autologin_password: 'generated-pw',
      }),
    ).toEqual({ email: 'admin@example.com', password: 'generated-pw' });
  });

  it('returns null for an ordinary config payload', () => {
    expect(readDevAutoLoginConfig({ password_auth_enabled: true })).toBeNull();
  });

  it('returns null for a partial or malformed pair', () => {
    expect(readDevAutoLoginConfig({ dev_autologin_email: 'a@b.com' })).toBeNull();
    expect(
      readDevAutoLoginConfig({ dev_autologin_email: 'a@b.com', dev_autologin_password: '' }),
    ).toBeNull();
    expect(
      readDevAutoLoginConfig({ dev_autologin_email: 1, dev_autologin_password: 2 }),
    ).toBeNull();
    expect(readDevAutoLoginConfig(null)).toBeNull();
  });
});

describe('dev auto-login suppression', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    (globalThis as { localStorage?: unknown }).localStorage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    };
  });

  afterEach(() => {
    delete (globalThis as { localStorage?: unknown }).localStorage;
  });

  it('round-trips a sign-out and a later manual sign-in', () => {
    expect(isDevAutoLoginSuppressed()).toBe(false);
    suppressDevAutoLogin();
    expect(isDevAutoLoginSuppressed()).toBe(true);
    clearDevAutoLoginSuppression();
    expect(isDevAutoLoginSuppressed()).toBe(false);
  });

  it('reports not-suppressed when storage is unavailable', () => {
    delete (globalThis as { localStorage?: unknown }).localStorage;
    expect(() => suppressDevAutoLogin()).not.toThrow();
    expect(isDevAutoLoginSuppressed()).toBe(false);
  });
});
