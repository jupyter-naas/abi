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
import {
  addFolder,
  folders,
  listUsers,
  makeFolder,
  moveNode,
  readFavorites,
  removeNode,
  renameFolder,
  togglePinned,
  writeFavorites,
  MAX_FOLDERS,
} from "@/lib/pins";
import type { DropTarget, FavoriteNode } from "@/lib/pins";
import { readSessionTimezone, writeSessionTimezone } from "@/lib/session";
import { landingPages, sectionOf } from "@/lib/appConfig";
import type { SectionKey } from "@/lib/appConfig";
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
  /** Last page visited in each section — where its rail link points back to.
   * Seeded from `config.yaml` with each section's first visible page. */
  sectionPages: Record<SectionKey, PageKey>;
  setSectionPage: (page: PageKey) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  /** The favorites bar: pinned authors and the folders filing them. */
  favorites: FavoriteNode[];
  /** Every pinned author, flat — what the pin buttons check themselves against. */
  pinnedUsers: string[];
  togglePinnedUser: (username: string) => void;
  /** Adds an empty folder at the end of the bar and returns its id, so the
   * caller can open it for naming right away. `null` when the cap is reached. */
  createFolder: () => string | null;
  renameFavoriteFolder: (id: string, name: string) => void;
  /** Drops a favorite or a whole folder from the bar. */
  removeFavorite: (id: string) => void;
  /** Reorders the bar, files an author into a folder, or takes one back out. */
  moveFavorite: (id: string, target: DropTarget) => void;
};

const AppStateContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<Snapshots | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scenarioId, setScenarioId] = useState("");
  const [querySlug, setQuerySlug] = useState("");
  const [timezone, setTimezoneState] = useState("UTC");
  const [sectionPages, setSectionPages] =
    useState<Record<SectionKey, PageKey>>(landingPages);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [favorites, setFavorites] = useState<FavoriteNode[]>([]);

  // Read after mount, never during render: the prerendered HTML knows nothing
  // about this browser's storage.
  useEffect(() => {
    setFavorites(readFavorites());
  }, []);

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
          `Failed to load snapshots: ${err.message}. Run the X app build to publish JSON under x/apps/x_proxy/.`,
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

  // Remembers the page inside its own section, so each rail link comes back to
  // where it was left.
  const setSectionPage = useCallback((page: PageKey) => {
    const section = sectionOf(page).key;
    setSectionPages((current) =>
      current[section] === page ? current : { ...current, [section]: page },
    );
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((value) => !value);
  }, []);

  // Every favorites edit is the same move: rewrite the bar with a pure
  // function from `lib/pins`, then persist exactly what is now on screen.
  const editFavorites = useCallback(
    (edit: (current: FavoriteNode[]) => FavoriteNode[]) => {
      setFavorites((current) => {
        const next = edit(current);
        if (next === current) return current;
        writeFavorites(next);
        return next;
      });
    },
    [],
  );

  const togglePinnedUser = useCallback(
    (username: string) => {
      editFavorites((current) => togglePinned(current, username));
    },
    [editFavorites],
  );

  // The id is handed back so the bar can open the new folder for naming, which
  // is why this reads the cap here instead of leaving it to `addFolder` alone.
  const createFolder = useCallback(() => {
    if (folders(favorites).length >= MAX_FOLDERS) return null;
    const folder = makeFolder();
    editFavorites((current) => addFolder(current, folder));
    return folder.id;
  }, [favorites, editFavorites]);

  const renameFavoriteFolder = useCallback(
    (id: string, name: string) => {
      editFavorites((current) => renameFolder(current, id, name));
    },
    [editFavorites],
  );

  const removeFavorite = useCallback(
    (id: string) => {
      editFavorites((current) => removeNode(current, id));
    },
    [editFavorites],
  );

  const moveFavorite = useCallback(
    (id: string, target: DropTarget) => {
      editFavorites((current) => moveNode(current, id, target));
    },
    [editFavorites],
  );

  const pinnedUsers = useMemo(() => listUsers(favorites), [favorites]);

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
      sectionPages,
      setSectionPage,
      sidebarCollapsed,
      toggleSidebar,
      favorites,
      pinnedUsers,
      togglePinnedUser,
      createFolder,
      renameFavoriteFolder,
      removeFavorite,
      moveFavorite,
    }),
    [
      data,
      error,
      scenarioId,
      querySlug,
      timezone,
      setTimezone,
      sectionPages,
      setSectionPage,
      sidebarCollapsed,
      toggleSidebar,
      favorites,
      pinnedUsers,
      togglePinnedUser,
      createFolder,
      renameFavoriteFolder,
      removeFavorite,
      moveFavorite,
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
