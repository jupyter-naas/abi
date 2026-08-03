'use client';

import { useEffect, useRef, useState } from 'react';
import type { GeoJSON as LeafletGeoJSON, Map as LeafletMap } from 'leaflet';
import { Loader2 } from 'lucide-react';
import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import { observeMapsLeafletSize } from '../lib/leaflet-map';
import {
  isMapsDarkMode,
  MAPS_TILE_ATTR,
  MAPS_TILE_DARK,
  MAPS_TILE_LIGHT,
} from '../lib/leaflet-tiles';
import './maps-components.css';

/**
 * Natural Earth 110m country borders. Maps-owned Public layer.
 */
export function MapsNaturalEarth() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LeafletGeoJSON | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [count, setCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function setup() {
      const L = await import('leaflet');
      await import('leaflet/dist/leaflet.css');
      if (cancelled || !containerRef.current) return;

      if (!mapRef.current) {
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

      try {
        const res = await fetch(MAPS_PUBLIC_FEEDS.naturalEarth, {
          signal: AbortSignal.timeout(20000),
        });
        if (!res.ok) throw new Error(`Natural Earth ${res.status}`);
        const gj = await res.json();
        if (cancelled || !mapRef.current) return;

        layerRef.current?.remove();
        const layer = L.geoJSON(gj, {
          style: {
            color: '#0f766e',
            weight: 1,
            fillOpacity: 0.04,
            opacity: 0.75,
          },
        }).addTo(mapRef.current);
        layerRef.current = layer;

        const features = Array.isArray(gj?.features) ? gj.features.length : 0;
        setCount(features);
        setStatus('ready');
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : 'Failed to load Natural Earth',
        );
        setStatus('error');
      }
    }

    void setup();
    return () => {
      cancelled = true;
      layerRef.current?.remove();
      layerRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className="maps-canvas">
      <div className="maps-canvas__toolbar">
        <span className="maps-canvas__toolbar-title">Natural Earth</span>
        {status === 'loading' ? (
          <span className="maps-status maps-status--row">
            <Loader2 size={14} className="animate-spin" />
            Loading borders…
          </span>
        ) : null}
        {status === 'ready' ? (
          <span className="maps-canvas__toolbar-meta">
            {count} countries · 110m · WSR border layer
          </span>
        ) : null}
        {status === 'error' ? (
          <span className="maps-status maps-status--error">
            {error ?? 'Natural Earth GeoJSON unavailable'}
          </span>
        ) : null}
      </div>
      <div className="maps-canvas__stage">
        <div ref={containerRef} className="maps-leaflet" />
      </div>
    </div>
  );
}
