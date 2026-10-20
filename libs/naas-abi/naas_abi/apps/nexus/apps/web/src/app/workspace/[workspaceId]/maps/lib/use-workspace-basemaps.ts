'use client';

import { useEffect, useMemo } from 'react';

import { useMapsStore, workspaceLayoutsOf } from '@/stores/maps';
import { basemapDefFromApi, normalizeBasemapId, type MapsBasemapDef } from './maps-basemaps';

/** The workspace basemap catalog (server state, see `/api/maps/catalog`). */
export function useWorkspaceBasemaps(workspaceId: string | null | undefined): {
  /** Basemaps shown in the map type picker (respects Settings → Maps visibility). */
  defs: MapsBasemapDef[];
  /** Full catalog including hidden ids (normalization, layer defaults, settings). */
  allDefs: MapsBasemapDef[];
  hidden: string[];
  defaultBasemapId: string;
  normalize: (id: string | null | undefined) => string;
} {
  const loadLayouts = useMapsStore((s) => s.loadLayouts);
  const catalog = useMapsStore((s) => workspaceLayoutsOf(s, workspaceId ?? null));

  useEffect(() => {
    if (workspaceId) void loadLayouts(workspaceId);
  }, [workspaceId, loadLayouts]);

  const allDefs = useMemo(() => catalog.basemaps.map(basemapDefFromApi), [catalog.basemaps]);
  const defs = useMemo(() => {
    const hidden = new Set(catalog.hiddenBasemaps);
    return allDefs.filter((def) => !hidden.has(def.id));
  }, [allDefs, catalog.hiddenBasemaps]);
  const { defaultBasemapId } = catalog;

  return {
    defs,
    allDefs,
    hidden: catalog.hiddenBasemaps,
    defaultBasemapId,
    normalize: (id) => normalizeBasemapId(id, allDefs, defaultBasemapId),
  };
}
