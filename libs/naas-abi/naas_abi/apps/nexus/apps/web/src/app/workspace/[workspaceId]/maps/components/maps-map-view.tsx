'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { MapsAllLayers } from './maps-all-layouts';
import { MapsLayerGeoJsonDebugPanel } from './maps-layer-geojson-debug-panel';
import { MapsMenuBar } from './maps-menu-bar';
import { MapsNewLayerModal } from './maps-new-layer-modal';
import { isMapsGeoJsonDebugEnabled } from '../lib/maps-layer-geojson-debug';
import { useMapLayers } from '../lib/use-map-layouts';
import { useMapsLayerParams } from '../lib/use-maps-layer-params';
import { mapsPath } from '../lib/maps-route';
import './maps-components.css';

export function MapsMapView() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [geoJsonLayersOpen, setGeoJsonLayersOpen] = useState(false);
  const { layerIds, rawLayerIds, defaultLayerIds, workspaceId } = useMapsLayerParams();

  useEffect(() => {
    if (isMapsGeoJsonDebugEnabled(searchParams)) setGeoJsonLayersOpen(true);
  }, [searchParams]);
  const { all, entries, loading, customLayerGroups, canEdit } = useMapLayers();
  const [newLayerOpen, setNewLayerOpen] = useState(false);

  useEffect(() => {
    if (isMobile || rawLayerIds.length > 0 || loading) return;
    if (!defaultLayerIds.length) return;
    router.replace(mapsPath(workspaceId, defaultLayerIds));
  }, [isMobile, rawLayerIds.length, loading, defaultLayerIds, router, workspaceId]);

  const subtitle = useMemo(() => {
    if (layerIds.length === 0) return 'Basemap';
    if (layerIds.length === 1) {
      return entries.find((e) => e.id === layerIds[0])?.title ?? 'Map';
    }
    return `${layerIds.length} active layers`;
  }, [entries, layerIds]);

  const takenLayerIds = useMemo(() => new Set(all.map((entry) => entry.id)), [all]);

  const menu = (
    <MapsMenuBar
      workspaceId={workspaceId}
      onNewLayer={() => setNewLayerOpen(true)}
      onGeoJsonLayers={() => setGeoJsonLayersOpen(true)}
    />
  );

  const onLayerCreated = useCallback(
    (layerId: string) => {
      const next = [...new Set([...layerIds, layerId])];
      router.push(mapsPath(workspaceId, next));
    },
    [layerIds, router, workspaceId],
  );

  return (
    <div className="maps-root">
      <div className="maps-header-gap">
        <Header title="Maps" subtitle={subtitle} nav={menu} />
      </div>
      <div className="maps-body">
        <MapsAllLayers layerIds={layerIds} />
        <MapsLayerGeoJsonDebugPanel
          open={geoJsonLayersOpen}
          onClose={() => setGeoJsonLayersOpen(false)}
        />
        {workspaceId ? (
          <MapsNewLayerModal
            open={newLayerOpen}
            onClose={() => setNewLayerOpen(false)}
            workspaceId={workspaceId}
            takenIds={takenLayerIds}
            customLayerGroups={customLayerGroups}
            canEdit={canEdit}
            onCreated={onLayerCreated}
          />
        ) : null}
      </div>
    </div>
  );
}
