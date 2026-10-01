'use client';

import { Fragment, createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { SETTINGS_CACHE_REFRESH_PATH } from '@/lib/settings-cache';
import { authFetch } from '@/stores/auth';
import { useAgentsStore } from '@/stores/agents';
import { useModelsStore } from '@/stores/models';
import { useSkillsStore } from '@/stores/skills';

type SettingsReloadValue = { reload: () => Promise<void>; reloading: boolean };

const SettingsReloadContext = createContext<SettingsReloadValue | null>(null);

/** Forget the stores' own short client-side caches so the remounted page fetches again. */
function resetClientCaches() {
  useAgentsStore.setState({ lastFetchedAt: {} });
  useSkillsStore.setState({ lastFetchedAt: {} });
  useModelsStore.setState({ lastFetchedAt: null });
}

/**
 * Wraps a settings tree. Reload drops the caller's entries from the backend's 24h
 * settings cache, then remounts the page so every API call it makes runs again.
 */
export function SettingsReloadProvider({
  children,
  onReload,
}: {
  children: ReactNode;
  /** Shared data the layout owns (not refetched by a page remount). */
  onReload?: () => Promise<unknown> | void;
}) {
  const [nonce, setNonce] = useState(0);
  const [reloading, setReloading] = useState(false);

  const reload = useCallback(async () => {
    setReloading(true);
    try {
      const response = await authFetch(SETTINGS_CACHE_REFRESH_PATH, { method: 'POST' });
      if (!response.ok) console.warn(`Settings cache refresh failed (HTTP ${response.status})`);
    } catch (error) {
      console.warn('Settings cache refresh failed:', error);
    }
    resetClientCaches();
    try {
      await onReload?.();
    } catch (error) {
      console.warn('Settings reload failed:', error);
    }
    setNonce((n) => n + 1);
    setReloading(false);
  }, [onReload]);

  return (
    <SettingsReloadContext.Provider value={{ reload, reloading }}>
      <Fragment key={nonce}>{children}</Fragment>
    </SettingsReloadContext.Provider>
  );
}

/** Reload button for settings page headers; renders nothing outside a settings tree. */
export function SettingsReloadButton({ className }: { className?: string }) {
  const context = useContext(SettingsReloadContext);
  if (!context) return null;
  return (
    <Button
      variant="secondary"
      onClick={() => void context.reload()}
      disabled={context.reloading}
      title="Reload: skip the 24h cache and fetch this page's data again"
      className={className}
    >
      <RefreshCw size={16} className={cn(context.reloading && 'animate-spin')} />
      Reload
    </Button>
  );
}
