'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ViewConfig } from './model';

/**
 * View definitions live in localStorage, per surface and workspace. They
 * describe how the user wants to look at the rows (which properties, which
 * filters, which grouping) — no server round-trip, and no reason to lose them
 * on reload.
 */

function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export interface DatabaseViewsOptions<K extends string, T extends string> {
  /** localStorage key prefix; the workspace id is appended. */
  storagePrefix: string;
  /** View layouts this surface offers, with their default name. */
  viewTypeLabels: Record<T, string>;
  /** Properties a view may reference (the title excluded from `visible`). */
  propertyKeys: readonly K[];
  titleKey: K;
  /** A fresh view of a layout: default visible properties and grouping. */
  createView: (type: T, name: string) => Omit<ViewConfig<K, T>, 'id'>;
  /** Views a workspace starts with. */
  defaultViews: () => Omit<ViewConfig<K, T>, 'id'>[];
}

export interface DatabaseViewsApi<K extends string = string, T extends string = string> {
  views: ViewConfig<K, T>[];
  activeView: ViewConfig<K, T>;
  activeViewId: string;
  selectView: (id: string) => void;
  addView: (type: T, name?: string) => void;
  updateActiveView: (patch: Partial<Omit<ViewConfig<K, T>, 'id'>>) => void;
  renameView: (id: string, name: string) => void;
  duplicateView: (id: string) => void;
  deleteView: (id: string) => void;
  /** False until localStorage has been read, so views never flash the default. */
  hydrated: boolean;
}

/** Drop anything that no longer matches the current property/view vocabulary. */
export function sanitizeViews<K extends string, T extends string>(
  raw: unknown,
  options: Pick<DatabaseViewsOptions<K, T>, 'viewTypeLabels' | 'propertyKeys' | 'titleKey' | 'createView'>,
): ViewConfig<K, T>[] | null {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const known = (key: unknown): key is K =>
    typeof key === 'string' && (options.propertyKeys as readonly string[]).includes(key);

  const views: ViewConfig<K, T>[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const view = item as Partial<ViewConfig<K, T>>;
    if (typeof view.id !== 'string' || typeof view.name !== 'string') continue;
    if (typeof view.type !== 'string' || !(view.type in options.viewTypeLabels)) continue;
    const type = view.type as T;
    views.push({
      id: view.id,
      name: view.name,
      type,
      visible: Array.isArray(view.visible)
        ? view.visible.filter(known).filter((key) => key !== options.titleKey)
        : [...options.createView(type, view.name).visible],
      filters: Array.isArray(view.filters)
        ? view.filters.filter(
            (f): f is ViewConfig<K, T>['filters'][number] =>
              !!f && typeof f === 'object' && known((f as { property?: unknown }).property),
          )
        : [],
      sort: view.sort && known(view.sort.property) ? view.sort : null,
      groupBy: known(view.groupBy) ? view.groupBy : null,
    });
  }
  return views.length > 0 ? views : null;
}

function withIds<K extends string, T extends string>(
  views: Omit<ViewConfig<K, T>, 'id'>[],
): ViewConfig<K, T>[] {
  return views.map((v) => ({ ...v, id: newId() }));
}

/** `opts` must be stable across renders: pass a module-level constant. */
export function useDatabaseViews<K extends string, T extends string>(
  workspaceId: string | null,
  opts: DatabaseViewsOptions<K, T>,
): DatabaseViewsApi<K, T> {

  const [views, setViews] = useState<ViewConfig<K, T>[]>(() => withIds(opts.defaultViews()));
  const [activeViewId, setActiveViewId] = useState<string>('');
  const [hydrated, setHydrated] = useState(false);

  const storageKey = workspaceId ? `${opts.storagePrefix}.${workspaceId}` : null;

  // Load on workspace change.
  useEffect(() => {
    if (!storageKey) return;
    setHydrated(false);
    let loaded = withIds(opts.defaultViews());
    let active = '';
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as { views?: unknown; activeViewId?: unknown };
        const clean = sanitizeViews(parsed.views, opts);
        if (clean) {
          loaded = clean;
          if (typeof parsed.activeViewId === 'string') active = parsed.activeViewId;
        }
      }
    } catch {
      // Corrupt or unavailable storage — fall back to the default views.
    }
    setViews(loaded);
    setActiveViewId(loaded.some((v) => v.id === active) ? active : loaded[0].id);
    setHydrated(true);
  }, [storageKey, opts]);

  // Persist on every change, once hydrated (so we never overwrite with defaults).
  useEffect(() => {
    if (!storageKey || !hydrated) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify({ views, activeViewId }));
    } catch {
      // Quota or private mode — views simply stay in memory for this session.
    }
  }, [storageKey, views, activeViewId, hydrated]);

  const activeView = useMemo(
    () => views.find((v) => v.id === activeViewId) ?? views[0],
    [views, activeViewId],
  );

  const selectView = useCallback((id: string) => setActiveViewId(id), []);

  const addView = useCallback(
    (type: T, name?: string) => {
      const view = { ...opts.createView(type, name ?? opts.viewTypeLabels[type]), id: newId() };
      setViews((prev) => [...prev, view]);
      setActiveViewId(view.id);
    },
    [opts],
  );

  const updateActiveView = useCallback(
    (patch: Partial<Omit<ViewConfig<K, T>, 'id'>>) => {
      setViews((prev) => prev.map((v) => (v.id === activeView.id ? { ...v, ...patch } : v)));
    },
    [activeView.id],
  );

  const renameView = useCallback((id: string, name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setViews((prev) => prev.map((v) => (v.id === id ? { ...v, name: trimmed } : v)));
  }, []);

  const duplicateView = useCallback(
    (id: string) => {
      const index = views.findIndex((v) => v.id === id);
      if (index < 0) return;
      const source = views[index];
      const copy: ViewConfig<K, T> = {
        ...source,
        id: newId(),
        name: `${source.name} copy`,
        visible: [...source.visible],
        filters: source.filters.map((f) => ({ ...f })),
      };
      setViews([...views.slice(0, index + 1), copy, ...views.slice(index + 1)]);
      setActiveViewId(copy.id);
    },
    [views],
  );

  const deleteView = useCallback(
    (id: string) => {
      // The last view is never removable — a database always has one view.
      if (views.length <= 1) return;
      const next = views.filter((v) => v.id !== id);
      setViews(next);
      if (activeViewId === id) setActiveViewId(next[0].id);
    },
    [views, activeViewId],
  );

  return {
    views,
    activeView,
    activeViewId: activeView.id,
    selectView,
    addView,
    updateActiveView,
    renameView,
    duplicateView,
    deleteView,
    hydrated,
  };
}
