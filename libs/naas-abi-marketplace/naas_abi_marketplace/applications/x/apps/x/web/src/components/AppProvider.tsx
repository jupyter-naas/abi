"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { loadSnapshots } from "@/lib/loadSnapshots";
import { readSessionTimezone, writeSessionTimezone } from "@/lib/session";
import type { PageKey, Snapshots } from "@/lib/types";

/**
 * State that outlives a page change.
 *
 * Each page of the app is its own route, so its component tree is thrown away
 * and rebuilt on every click. This provider is mounted by the root layout,
 * which Next keeps across client-side navigation — so the snapshots are fetched
 * once per session rather than once per page, and the filters, timezone and
 * sidebar survive moving between pages.
 */
type AppState = {
  data: Snapshots | null;
  error: string | null;
  scenarioId: string;
  setScenarioId: (id: string) => void;
  querySlug: string;
  setQuerySlug: (slug: string) => void;
  timezone: string;
  setTimezone: (id: string) => void;
  /** Last Posts subpage visited — where the Posts section link points back to. */
  postsPage: PageKey;
  setPostsPage: (page: PageKey) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
};

const AppStateContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<Snapshots | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scenarioId, setScenarioId] = useState("");
  const [querySlug, setQuerySlug] = useState("");
  const [timezone, setTimezoneState] = useState("UTC");
  const [postsPage, setPostsPage] = useState<PageKey>("count");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadSnapshots()
      .then((snap) => {
        if (cancelled) return;
        setData(snap);
        // A page opened from a link may already have applied its own filters
        // from the URL, so these only fill in what is still unset.
        setScenarioId((prev) => prev || snap.scenarios[0]?.id || "");
        setQuerySlug((prev) => prev || snap.queries[0]?.slug || "");
        const saved = readSessionTimezone();
        const allowed = new Set(snap.timezones.map((tz) => tz.id));
        setTimezoneState(
          saved && allowed.has(saved) ? saved : snap.defaultTimezone || "UTC",
        );
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(
          `Failed to load snapshots: ${err.message}. Run the X app build to publish JSON under x/apps/x/.`,
        );
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setTimezone = useCallback((id: string) => {
    setTimezoneState(id);
    writeSessionTimezone(id);
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((value) => !value);
  }, []);

  const value = useMemo<AppState>(
    () => ({
      data,
      error,
      scenarioId,
      setScenarioId,
      querySlug,
      setQuerySlug,
      timezone,
      setTimezone,
      postsPage,
      setPostsPage,
      sidebarCollapsed,
      toggleSidebar,
    }),
    [
      data,
      error,
      scenarioId,
      querySlug,
      timezone,
      setTimezone,
      postsPage,
      sidebarCollapsed,
      toggleSidebar,
    ],
  );

  return (
    <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
  );
}

export function useAppState(): AppState {
  const state = useContext(AppStateContext);
  if (!state) throw new Error("useAppState must be used inside AppProvider");
  return state;
}
