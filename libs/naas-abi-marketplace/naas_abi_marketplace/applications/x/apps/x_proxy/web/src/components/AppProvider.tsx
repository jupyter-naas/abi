"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { loadSnapshots, emptySnapshots } from "@/lib/loadSnapshots";
import {
  addFolder,
  folders,
  listIds,
  makeFolder,
  moveNode,
  readFavorites,
  removeNode,
  renameFolder,
  togglePinned,
  writeFavorites,
  MAX_FOLDERS,
} from "@/lib/pins";
import type {
  DropTarget,
  FavoriteLink,
  FavoriteNode,
  FavoritesScope,
} from "@/lib/pins";

const SCOPES: FavoritesScope[] = ["users", "posts"];

type ScopedFavorites = Record<FavoritesScope, FavoriteNode[]>;

const EMPTY_FAVORITES: ScopedFavorites = { users: [], posts: [] };
import { readSessionTimezone, writeSessionTimezone } from "@/lib/session";
import { landingPages, sectionLandingPage, sectionOf } from "@/lib/appConfig";
import type { SectionKey } from "@/lib/appConfig";
import type { PageKey, Snapshots } from "@/lib/types";

/**
 * State that outlives a page change.
 *
 * Each page of the app is its own route, so its component tree is thrown away
 * and rebuilt on every click. This provider is mounted by the root layout,
 * which Next keeps across client-side navigation - so the snapshots are fetched
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
  /** Last page visited in each section - where its rail link points back to.
   * Seeded from `config.yaml` with each section's first visible page. */
  sectionPages: Record<SectionKey, PageKey>;
  setSectionPage: (page: PageKey) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  /**
   * The favorites bars - one of pinned authors, one of pinned posts, each with
   * its own folders. They never mix; `favorites:` in `config.yaml` says which
   * bar a page shows.
   */
  favorites: ScopedFavorites;
  /** Ids pinned in each bar - what the pin buttons check themselves against. */
  pinnedIds: Record<FavoritesScope, string[]>;
  /** Pins or unpins one link in its bar. */
  togglePinned: (scope: FavoritesScope, link: FavoriteLink) => void;
  /** Adds an empty folder at the end of a bar and returns its id, so the
   * caller can open it for naming right away. `null` when the cap is reached. */
  createFolder: (scope: FavoritesScope) => string | null;
  renameFavoriteFolder: (
    scope: FavoritesScope,
    id: string,
    name: string,
  ) => void;
  /** Drops a favorite or a whole folder from a bar. */
  removeFavorite: (scope: FavoritesScope, id: string) => void;
  /** Reorders a bar, files a favorite into a folder, or takes one back out. */
  moveFavorite: (
    scope: FavoritesScope,
    id: string,
    target: DropTarget,
  ) => void;
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
  const [favorites, setFavorites] = useState<ScopedFavorites>(EMPTY_FAVORITES);

  // Read after mount, never during render: the prerendered HTML knows nothing
  // about this browser's storage.
  useEffect(() => {
    setFavorites({ users: readFavorites("users"), posts: readFavorites("posts") });
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
        setData(emptySnapshots());
        setTimezoneState("UTC");
        setError(
          `Snapshots unavailable (${err.message}). Showing empty data — run the X app build to publish JSON under x/apps/x_proxy/.`,
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
  // where it was left. Detail pages that are not tabs (a post, an author) map
  // to the tab they belong under, so Posts never reopens a post when a tab was
  // meant.
  const setSectionPage = useCallback((page: PageKey) => {
    const section = sectionOf(page).key;
    const landing = sectionLandingPage(page);
    setSectionPages((current) =>
      current[section] === landing ? current : { ...current, [section]: landing },
    );
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((value) => !value);
  }, []);

  // Every favorites edit is the same move: rewrite one bar with a pure function
  // from `lib/pins`, then persist exactly what is now on screen.
  const editFavorites = useCallback(
    (
      scope: FavoritesScope,
      edit: (current: FavoriteNode[]) => FavoriteNode[],
    ) => {
      setFavorites((current) => {
        const next = edit(current[scope]);
        if (next === current[scope]) return current;
        writeFavorites(scope, next);
        return { ...current, [scope]: next };
      });
    },
    [],
  );

  const togglePinnedLink = useCallback(
    (scope: FavoritesScope, link: FavoriteLink) => {
      editFavorites(scope, (current) => togglePinned(current, link));
    },
    [editFavorites],
  );

  // The id is handed back so the bar can open the new folder for naming, which
  // is why this reads the cap here instead of leaving it to `addFolder` alone.
  const createFolder = useCallback(
    (scope: FavoritesScope) => {
      if (folders(favorites[scope]).length >= MAX_FOLDERS) return null;
      const folder = makeFolder();
      editFavorites(scope, (current) => addFolder(current, folder));
      return folder.id;
    },
    [favorites, editFavorites],
  );

  const renameFavoriteFolder = useCallback(
    (scope: FavoritesScope, id: string, name: string) => {
      editFavorites(scope, (current) => renameFolder(current, id, name));
    },
    [editFavorites],
  );

  const removeFavorite = useCallback(
    (scope: FavoritesScope, id: string) => {
      editFavorites(scope, (current) => removeNode(current, id));
    },
    [editFavorites],
  );

  const moveFavorite = useCallback(
    (scope: FavoritesScope, id: string, target: DropTarget) => {
      editFavorites(scope, (current) => moveNode(current, id, target));
    },
    [editFavorites],
  );

  const pinnedIds = useMemo(
    () =>
      Object.fromEntries(
        SCOPES.map((scope) => [scope, listIds(favorites[scope])]),
      ) as Record<FavoritesScope, string[]>,
    [favorites],
  );

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
      pinnedIds,
      togglePinned: togglePinnedLink,
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
      pinnedIds,
      togglePinnedLink,
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
