'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  DEFAULT_VISIBLE,
  PROPERTY_BY_KEY,
  VIEW_TYPE_LABELS,
  type PropertyKey,
  type ViewConfig,
  type ViewType,
} from './types';

/**
 * View definitions live in localStorage, per workspace. They describe how the
 * user wants to look at their apps (which properties, which filters, which
 * grouping) — no server round-trip, and no reason to lose them on reload.
 */

const STORAGE_PREFIX = 'nexus.apps.views';

function storageKey(workspaceId: string): string {
  return `${STORAGE_PREFIX}.${workspaceId}`;
}

function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function createView(type: ViewType, name?: string): ViewConfig {
  return {
    id: newId(),
    name: name ?? VIEW_TYPE_LABELS[type],
    type,
    visible: [...DEFAULT_VISIBLE[type]],
    filters: [],
    sort: null,
    groupBy: type === 'board' ? 'module' : null,
  };
}

function defaultViews(): ViewConfig[] {
  return [createView('gallery', 'Gallery')];
}

/** Drop anything that no longer matches the current property/view vocabulary. */
function sanitize(raw: unknown): ViewConfig[] | null {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const known = (key: unknown): key is PropertyKey =>
    typeof key === 'string' && key in PROPERTY_BY_KEY;

  const views: ViewConfig[] = [];
  for (const item of raw) {
    if (!item || typeof item !== 'object') continue;
    const view = item as Partial<ViewConfig>;
    if (typeof view.id !== 'string' || typeof view.name !== 'string') continue;
    if (typeof view.type !== 'string' || !(view.type in VIEW_TYPE_LABELS)) continue;
    const type = view.type as ViewType;
    views.push({
      id: view.id,
      name: view.name,
      type,
      visible: Array.isArray(view.visible)
        ? view.visible.filter(known).filter((key) => key !== 'name')
        : [...DEFAULT_VISIBLE[type]],
      filters: Array.isArray(view.filters)
        ? view.filters.filter(
            (f): f is ViewConfig['filters'][number] =>
              !!f && typeof f === 'object' && known((f as { property?: unknown }).property),
          )
        : [],
      sort: view.sort && known(view.sort.property) ? view.sort : null,
      groupBy: known(view.groupBy) ? view.groupBy : null,
    });
  }
  return views.length > 0 ? views : null;
}

export interface AppViewsApi {
  views: ViewConfig[];
  activeView: ViewConfig;
  activeViewId: string;
  selectView: (id: string) => void;
  addView: (type: ViewType, name?: string) => void;
  updateActiveView: (patch: Partial<Omit<ViewConfig, 'id'>>) => void;
  renameView: (id: string, name: string) => void;
  duplicateView: (id: string) => void;
  deleteView: (id: string) => void;
  /** False until localStorage has been read, so views never flash the default. */
  hydrated: boolean;
}

export function useAppViews(workspaceId: string | null): AppViewsApi {
  const [views, setViews] = useState<ViewConfig[]>(defaultViews);
  const [activeViewId, setActiveViewId] = useState<string>(() => '');
  const [hydrated, setHydrated] = useState(false);

  // Load on workspace change.
  useEffect(() => {
    if (!workspaceId) return;
    setHydrated(false);
    let loaded = defaultViews();
    let active = '';
    try {
      const raw = localStorage.getItem(storageKey(workspaceId));
      if (raw) {
        const parsed = JSON.parse(raw) as { views?: unknown; activeViewId?: unknown };
        const clean = sanitize(parsed.views);
        if (clean) {
          loaded = clean;
          if (typeof parsed.activeViewId === 'string') active = parsed.activeViewId;
        }
      }
    } catch {
      // Corrupt or unavailable storage — fall back to the default gallery view.
    }
    setViews(loaded);
    setActiveViewId(loaded.some((v) => v.id === active) ? active : loaded[0].id);
    setHydrated(true);
  }, [workspaceId]);

  // Persist on every change, once hydrated (so we never overwrite with defaults).
  useEffect(() => {
    if (!workspaceId || !hydrated) return;
    try {
      localStorage.setItem(storageKey(workspaceId), JSON.stringify({ views, activeViewId }));
    } catch {
      // Quota or private mode — views simply stay in memory for this session.
    }
  }, [workspaceId, views, activeViewId, hydrated]);

  const activeView = useMemo(
    () => views.find((v) => v.id === activeViewId) ?? views[0],
    [views, activeViewId],
  );

  const selectView = useCallback((id: string) => setActiveViewId(id), []);

  const addView = useCallback((type: ViewType, name?: string) => {
    const view = createView(type, name);
    setViews((prev) => [...prev, view]);
    setActiveViewId(view.id);
  }, []);

  const updateActiveView = useCallback(
    (patch: Partial<Omit<ViewConfig, 'id'>>) => {
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
      const copy: ViewConfig = {
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
