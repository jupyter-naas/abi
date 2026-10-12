'use client';

import { useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Header } from '@/components/shell/header';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { MapsAllLayers } from './maps-all-layouts';
import { MapsMenuBar } from './maps-menu-bar';
import { useMapLayers } from '../lib/use-map-layouts';
import { useMapsLayerParams } from '../lib/use-maps-layer-params';
import { mapsPath } from '../lib/maps-route';
import './maps-components.css';

export function MapsMapView() {
  const isMobile = useIsMobile();
  const router = useRouter();
  const { layerIds, rawLayerIds, defaultLayerIds, workspaceId } = useMapsLayerParams();
  const { entries, canEdit, loading } = useMapLayers();

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

  const menu = <MapsMenuBar workspaceId={workspaceId} canEdit={canEdit} />;

  return (
    <div className="maps-root">
      <div className="maps-header-gap">
        <Header title="Maps" subtitle={subtitle} nav={menu} />
      </div>
      <div className="maps-body">
        <MapsAllLayers layerIds={layerIds} />
      </div>
    </div>
  );
}
