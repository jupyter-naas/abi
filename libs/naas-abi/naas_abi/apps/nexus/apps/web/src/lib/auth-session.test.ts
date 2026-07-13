import { describe, expect, it } from 'vitest';

import { mergeAuthPersistedState } from './auth-session';

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
