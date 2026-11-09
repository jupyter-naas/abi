import { describe, expect, it } from 'vitest';

import { mergeAuthPersistedState, safeNextPath } from './auth-session';

describe('mergeAuthPersistedState', () => {
  const current = {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  };

  it('takes the stored user and signed-in flag', () => {
    const merged = mergeAuthPersistedState(
      { user: { id: '2', email: 'c@d.com', name: 'C' }, isAuthenticated: true },
      current,
    );
    expect(merged.user).toEqual({ id: '2', email: 'c@d.com', name: 'C' });
    expect(merged.isAuthenticated).toBe(true);
  });

  it('never adopts a token an older snapshot held', () => {
    const merged = mergeAuthPersistedState(
      { user: null, token: 'old', refreshToken: 'old', sessionKind: 'bearer', isAuthenticated: true },
      current,
    );
    expect(JSON.stringify(merged)).not.toContain('old');
    expect('token' in merged).toBe(false);
  });

  it('starts signed out from an empty snapshot', () => {
    expect(mergeAuthPersistedState(undefined, current).isAuthenticated).toBe(false);
  });
});

describe('safeNextPath', () => {
  it('keeps a path on this app', () => {
    expect(safeNextPath('/workspace/w/chat')).toBe('/workspace/w/chat');
  });

  it.each(['https://evil.test', '//evil.test', '/\\evil.test', null, ''])('refuses %s', (value) => {
    expect(safeNextPath(value as string | null)).toBe('/');
  });
});
