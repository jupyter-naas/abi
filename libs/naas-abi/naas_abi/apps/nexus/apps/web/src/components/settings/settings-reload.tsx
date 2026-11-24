'use client';

import { Fragment, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { SETTINGS_CACHE_REFRESH_PATH, isCachedSettingsRoute } from '@/lib/settings-cache';
import { authFetch } from '@/stores/auth';
import { clearResources } from '@/lib/resource-cache';
import { forgetAgentsSync, useAgentsStore } from '@/stores/agents';
import { useModelsStore } from '@/stores/models';
import { useSkillsStore } from '@/stores/skills';

type SettingsReloadValue = {
  reload: () => Promise<void>;
  reloading: boolean;
  /** Bumped by each Reload, for the pages that read again themselves. */
  generation: number;
  /** A page that reads again on `generation` registers while mounted. */
  register: () => () => void;
};

const SettingsReloadContext = createContext<SettingsReloadValue | null>(null);

/** Forget the stores' own short client-side caches so the remounted page fetches again. */
function resetClientCaches() {
  clearResources();
  forgetAgentsSync();
  useAgentsStore.setState({ lastFetchedAt: {} });
  useSkillsStore.setState({ lastFetchedAt: {} });
  useModelsStore.setState({ lastFetchedAt: null });
}

/**
 * Wraps a settings tree. Reload drops the caller's entries from the backend's 24h
 * settings cache and the client's caches, then has the page read again: a page that
 * reads on `useSettingsReloadGeneration` does it in place, keeping what the user typed,
 * its filters and its scroll; any other page is remounted, as before, so every API call
 * it makes runs again.
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
  const [generation, setGeneration] = useState(0);
  const [reloading, setReloading] = useState(false);
  const readers = useRef(0);
  const register = useCallback(() => {
    readers.current += 1;
    return () => {
      readers.current -= 1;
    };
  }, []);

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
    if (readers.current > 0) setGeneration((n) => n + 1);
    else setNonce((n) => n + 1);
    setReloading(false);
  }, [onReload]);

  const value = useMemo(
    () => ({ reload, reloading, generation, register }),
    [reload, reloading, generation, register]
  );
  return (
    <SettingsReloadContext.Provider value={value}>
      <Fragment key={nonce}>{children}</Fragment>
    </SettingsReloadContext.Provider>
  );
}

/**
 * For a page that reads its data again itself on Reload (put the number in the effects
 * that read): Reload then leaves it mounted. 0 outside a settings tree.
 */
export function useSettingsReloadGeneration(): number {
  const context = useContext(SettingsReloadContext);
  const register = context?.register;
  useEffect(() => register?.(), [register]);
  return context?.generation ?? 0;
}

/**
 * Reload button for settings page headers. Shown on the cached settings pages only
 * (Components and Members); renders nothing elsewhere or outside a settings tree.
 */
export function SettingsReloadButton({ className }: { className?: string }) {
  const context = useContext(SettingsReloadContext);
  const pathname = usePathname();
  if (!context || !isCachedSettingsRoute(pathname ?? '')) return null;
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
