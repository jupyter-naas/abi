import { describe, expect, it } from 'vitest';

import { mergeAuthPersistedState, shouldSkipMagicLinkConfirmation } from './auth-session';

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
