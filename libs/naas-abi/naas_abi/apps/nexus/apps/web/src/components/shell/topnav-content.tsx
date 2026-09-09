'use client';

import { createContext, useContext, useEffect, useLayoutEffect, useState, type ReactNode } from 'react';
import { usePathname } from 'next/navigation';

/**
 * Pages declare their topnav content by rendering `<Header title=... />`.
 * `Header` only registers it here; `TopNav` (mounted once by WorkspaceLayout,
 * spanning the width above main content and the AI chat pane) reads it and
 * paints the actual bar. Keyed by pathname so a route without a Header falls
 * through to an empty bar instead of inheriting the previous page's content.
 */
interface TopNavEntry {
  title?: string;
  subtitle?: string;
  nav?: ReactNode;
  actions?: ReactNode;
  pathname: string;
}

type RegisterTopNav = (entry: TopNavEntry) => void;

const TopNavStateContext = createContext<TopNavEntry | null>(null);
const TopNavRegisterContext = createContext<RegisterTopNav>(() => {});

export function TopNavProvider({ children }: { children: ReactNode }) {
  const [entry, setEntry] = useState<TopNavEntry | null>(null);

  return (
    <TopNavRegisterContext.Provider value={setEntry}>
      <TopNavStateContext.Provider value={entry}>{children}</TopNavStateContext.Provider>
    </TopNavRegisterContext.Provider>
  );
}

// Register before paint so a route change swaps content in the same frame as
// the page, instead of flashing the previous page's bar. useEffect on the
// server, where layout effects do not run.
const useRegisterEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

export function useRegisterTopNav(entry: Omit<TopNavEntry, 'pathname'>): void {
  const register = useContext(TopNavRegisterContext);
  const pathname = usePathname();
  const { title, subtitle, nav, actions } = entry;

  useRegisterEffect(() => {
    register({ title, subtitle, nav, actions, pathname });
  }, [register, title, subtitle, nav, actions, pathname]);
}

export function useTopNavContent(): {
  title?: string;
  subtitle?: string;
  nav?: ReactNode;
  actions?: ReactNode;
} {
  const entry = useContext(TopNavStateContext);
  const pathname = usePathname();

  if (!entry || !pathname || entry.pathname !== pathname) return {};
  return { title: entry.title, subtitle: entry.subtitle, nav: entry.nav, actions: entry.actions };
}
