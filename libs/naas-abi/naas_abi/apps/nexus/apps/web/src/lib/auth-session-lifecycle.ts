import { setAuthFlagCookie } from './auth-session';
import { useAuthStore } from '@/stores/auth';

/**
 * Keep the session in step with the API, including after browser sleep and
 * network recovery: the API refreshes it at the provider, this re-reads it
 * (the user, and the CSRF token, which lives in memory only).
 */
export function startAuthSessionLifecycle(): () => void {
  const renew = () => {
    if (!useAuthStore.persist.hasHydrated()) return;
    const state = useAuthStore.getState();
    if (!state.isAuthenticated) return;
    setAuthFlagCookie();
    void state.adoptCookieSession();
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key === 'nexus-auth') renew();
  };
  const unsubscribe = useAuthStore.persist.onFinishHydration(renew);
  const timer = window.setInterval(renew, 300000);
  window.addEventListener('focus', renew);
  window.addEventListener('online', renew);
  window.addEventListener('pageshow', renew);
  window.addEventListener('storage', onStorage);
  document.addEventListener('visibilitychange', renew);
  renew();
  return () => {
    unsubscribe();
    window.clearInterval(timer);
    window.removeEventListener('focus', renew);
    window.removeEventListener('online', renew);
    window.removeEventListener('pageshow', renew);
    window.removeEventListener('storage', onStorage);
    document.removeEventListener('visibilitychange', renew);
  };
}
