import { shouldRefreshAccessToken, setAuthFlagCookie } from './auth-session';
import { syncPersistedAuthSession, useAuthStore } from '@/stores/auth';

/** Keep sessions renewed, including after browser sleep and network recovery. */
export function startAuthSessionLifecycle(): () => void {
  const renew = () => {
    if (!useAuthStore.persist.hasHydrated()) return;
    syncPersistedAuthSession();
    const state = useAuthStore.getState();
    if (!state.refreshToken) return;
    setAuthFlagCookie();
    if (shouldRefreshAccessToken(state.token)) void state.refreshAccessToken();
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key === 'nexus-auth') renew();
  };
  const unsubscribe = useAuthStore.persist.onFinishHydration(renew);
  const timer = window.setInterval(renew, 30000);
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
