'use client';

import { createContext, useContext, useEffect, useLayoutEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { resolveShellTitle, type ShellTitleEntry } from './shell-title-entry';

/**
 * Pages already declare their title by rendering `<Header title=... />`.
 * The desktop header does not paint it, but the mobile top bar needs it, and
 * only the page knows things like "Local Folder / Invoices" vs plain "Files".
 * So Header registers here and the mobile chrome reads it, instead of a second
 * pathname-to-label table that drifts every time a route is added.
 */
type RegisterShellTitle = (entry: ShellTitleEntry) => void;

const ShellTitleStateContext = createContext<ShellTitleEntry | null>(null);
const ShellTitleRegisterContext = createContext<RegisterShellTitle>(() => {});

export function ShellTitleProvider({ children }: { children: React.ReactNode }) {
  const [entry, setEntry] = useState<ShellTitleEntry | null>(null);

  return (
    <ShellTitleRegisterContext.Provider value={setEntry}>
      <ShellTitleStateContext.Provider value={entry}>{children}</ShellTitleStateContext.Provider>
    </ShellTitleRegisterContext.Provider>
  );
}

// Register before paint so a route change swaps the title in the same frame as
// the page, instead of flashing the fallback. useEffect on the server, where
// layout effects do not run.
const useRegisterEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

export function useRegisterShellTitle(title?: string, subtitle?: string): void {
  const register = useContext(ShellTitleRegisterContext);
  const pathname = usePathname();

  useRegisterEffect(() => {
    register({ title, subtitle, pathname });
  }, [register, title, subtitle, pathname]);
}

export function useShellTitle(): { title?: string; subtitle?: string } {
  const entry = useContext(ShellTitleStateContext);
  const pathname = usePathname();

  return resolveShellTitle(entry, pathname);
}
