'use client';

import { useEffect, useRef } from 'react';
import type { Map as LeafletMap } from 'leaflet';
import { observeMapsLeafletSize } from '../lib/leaflet-map';
import {
  isMapsDarkMode,
  MAPS_TILE_ATTR,
  MAPS_TILE_DARK,
  MAPS_TILE_LIGHT,
} from '../lib/leaflet-tiles';
import './maps-components.css';

/**
 * Public OSM basemap canvas. Same tile stack Maps already uses for presence;
 * registered as its own Public source so the library matches Search's Public bucket.
 */
export function MapsOpenStreetMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function setup() {
      const L = await import('leaflet');
      await import('leaflet/dist/leaflet.css');
      if (cancelled || !containerRef.current || mapRef.current) return;

      const map = L.map(containerRef.current, {
        zoomControl: true,
        attributionControl: true,
      });
      L.tileLayer(isMapsDarkMode() ? MAPS_TILE_DARK : MAPS_TILE_LIGHT, {
        attribution: MAPS_TILE_ATTR,
        maxZoom: 18,
      }).addTo(map);
      map.setView([20, 0], 2);
      observeMapsLeafletSize(map);
      mapRef.current = map;
    }

    void setup();
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className="maps-canvas">
      <div className="maps-canvas__toolbar">
        <span className="maps-canvas__toolbar-title">OpenStreetMap</span>
        <span className="maps-canvas__toolbar-meta">
          Public basemap · OSM / CARTO
        </span>
      </div>
      <div className="maps-canvas__stage">
        <div ref={containerRef} className="maps-leaflet" />
      </div>
    </div>
  );
}
