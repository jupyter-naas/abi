import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { startAuthSessionLifecycle } from './auth-session-lifecycle';

const { state } = vi.hoisted(() => ({
  state: { isAuthenticated: true, adoptCookieSession: vi.fn() },
}));
vi.mock('@/stores/auth', () => ({
  useAuthStore: {
    getState: () => state,
    persist: { hasHydrated: () => true, onFinishHydration: () => vi.fn() },
  },
}));
let stop: () => void;

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('window', Object.assign(new EventTarget(), { setInterval, clearInterval }));
  vi.stubGlobal('document', Object.assign(new EventTarget(), { cookie: '' }));
  state.isAuthenticated = true;
  state.adoptCookieSession.mockClear();
});
afterEach(() => { stop?.(); vi.useRealTimers(); vi.unstubAllGlobals(); });

it('re-reads the session on a timer and removes it on unmount', () => {
  stop = startAuthSessionLifecycle();
  expect(state.adoptCookieSession).toHaveBeenCalledTimes(1); // at start
  vi.advanceTimersByTime(300000);
  expect(state.adoptCookieSession).toHaveBeenCalledTimes(2);
  stop();
  vi.advanceTimersByTime(300000);
  expect(state.adoptCookieSession).toHaveBeenCalledTimes(2);
});

it.each(['focus', 'online', 'pageshow'])('re-reads the session on %s after browser sleep', (event) => {
  stop = startAuthSessionLifecycle();
  state.adoptCookieSession.mockClear();
  window.dispatchEvent(new Event(event));
  expect(state.adoptCookieSession).toHaveBeenCalledTimes(1);
});

it('re-reads the session when visibility changes', () => {
  stop = startAuthSessionLifecycle();
  state.adoptCookieSession.mockClear();
  document.dispatchEvent(new Event('visibilitychange'));
  expect(state.adoptCookieSession).toHaveBeenCalledTimes(1);
});

it('does not touch a signed-out session', () => {
  state.isAuthenticated = false;
  stop = startAuthSessionLifecycle();
  vi.advanceTimersByTime(300000);
  expect(state.adoptCookieSession).not.toHaveBeenCalled();
});
