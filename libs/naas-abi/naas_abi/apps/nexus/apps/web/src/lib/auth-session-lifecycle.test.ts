import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { startAuthSessionLifecycle } from './auth-session-lifecycle';
import { shouldRefreshAccessToken } from './auth-session';

const { state, sync } = vi.hoisted(() => ({
  state: { token: '', refreshToken: 'refresh', refreshAccessToken: vi.fn() },
  sync: vi.fn(),
}));
vi.mock('@/stores/auth', () => ({
  syncPersistedAuthSession: sync,
  useAuthStore: {
    getState: () => state,
    persist: { hasHydrated: () => true, onFinishHydration: () => vi.fn() },
  },
}));
const jwt = (expires: number) => `header.${btoa(JSON.stringify({ exp: expires }))}.signature`;
let stop: () => void;

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('window', Object.assign(new EventTarget(), { setInterval, clearInterval }));
  vi.stubGlobal('document', Object.assign(new EventTarget(), { cookie: '' }));
  state.token = jwt(Date.now() / 1000 + 120);
  state.refreshAccessToken.mockClear();
  state.refreshToken = 'refresh';
});
afterEach(() => { stop?.(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it('renews before expiry and removes its timer on unmount', () => {
  stop = startAuthSessionLifecycle();
  expect(state.refreshAccessToken).not.toHaveBeenCalled();
  vi.advanceTimersByTime(60000);
  expect(state.refreshAccessToken).toHaveBeenCalledTimes(1);
  stop();
  vi.advanceTimersByTime(60000);
  expect(state.refreshAccessToken).toHaveBeenCalledTimes(1);
});

it.each(['focus', 'online', 'pageshow'])('renews on %s after browser sleep', (event) => {
  stop = startAuthSessionLifecycle();
  state.token = jwt(Date.now() / 1000 - 1);
  window.dispatchEvent(new Event(event));
  expect(state.refreshAccessToken).toHaveBeenCalledTimes(1);
});

it('renews when visibility changes', () => {
  stop = startAuthSessionLifecycle();
  state.token = jwt(Date.now() / 1000 - 1);
  document.dispatchEvent(new Event('visibilitychange'));
  expect(state.refreshAccessToken).toHaveBeenCalledTimes(1);
});

it('does not renew a logged-out session', () => {
  state.refreshToken = '';
  state.token = '';
  stop = startAuthSessionLifecycle();
  vi.advanceTimersByTime(60000);
  expect(state.refreshAccessToken).not.toHaveBeenCalled();
});

it('handles absent and malformed tokens without throwing', () => {
  expect(shouldRefreshAccessToken(null)).toBe(true);
  expect(shouldRefreshAccessToken('bad')).toBe(true);
  expect(shouldRefreshAccessToken(jwt(Date.now() / 1000 + 1800))).toBe(false);
});
