'use client';

import { useIsMobile } from '@/hooks/use-is-mobile';
import { useMapsLayerParams } from './lib/use-maps-layer-params';
import { MapsMapView } from './components/maps-map-view';

/**
 * Desktop: map canvas (layers from `?layer=` query params).
 * Mobile: layer list lives in the shell; map shows when `layer` params are set.
 */
export default function MapsPage() {
  const isMobile = useIsMobile();
  const { layerIds } = useMapsLayerParams();

  if (isMobile && layerIds.length === 0) {
    return null;
  }

  return <MapsMapView />;
}
