'use client';

import { useEffect, useRef, useState } from 'react';
import type { Map as LeafletMap, Marker } from 'leaflet';
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

interface QuakePin {
  id: string;
  lat: number;
  lng: number;
  label: string;
  mag: number;
}

/**
 * USGS earthquakes (M≥2.5, past day). Maps-owned Public layer.
 */
export function MapsEarthquakes() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
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
        const res = await fetch(MAPS_PUBLIC_FEEDS.earthquakes, {
          signal: AbortSignal.timeout(15000),
        });
        if (!res.ok) throw new Error(`USGS ${res.status}`);
        const gj = (await res.json()) as {
          features?: Array<{
            id?: string;
            properties?: { mag?: number; place?: string; time?: number };
            geometry?: { coordinates?: number[] };
          }>;
        };

        const pins: QuakePin[] = [];
        for (const f of gj.features ?? []) {
          const coords = f.geometry?.coordinates;
          if (!coords || coords.length < 2) continue;
          const [lng, lat] = coords;
          if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
          const mag = f.properties?.mag ?? 0;
          pins.push({
            id: String(f.id ?? `${lat},${lng}`),
            lat,
            lng,
            mag,
            label: `M${mag.toFixed(1)} · ${f.properties?.place ?? 'Earthquake'}`,
          });
        }

        if (cancelled || !mapRef.current) return;
        const map = mapRef.current;
        markersRef.current.forEach((m) => m.remove());
        markersRef.current = [];
        const bounds: [number, number][] = [];

        for (const pin of pins) {
          const size = Math.min(18, Math.max(8, 6 + pin.mag * 2));
          const icon = L.divIcon({
            className: 'maps-pin-icon',
            html: `<span style="display:block;width:${size}px;height:${size}px;border:2px solid #fff;background:#ea580c;box-shadow:0 1px 4px rgba(0,0,0,.35);border-radius:var(--org-border-radius,0px)"></span>`,
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
          });
          const marker = L.marker([pin.lat, pin.lng], { icon }).addTo(map);
          marker.bindPopup(
            `<div class="maps-pin-popup"><strong>${pin.label}</strong></div>`,
          );
          markersRef.current.push(marker);
          bounds.push([pin.lat, pin.lng]);
        }

        if (bounds.length > 1) {
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 5 });
        } else if (bounds.length === 1) {
          map.setView(bounds[0], 4);
        }

        setCount(pins.length);
        setStatus('ready');
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load USGS feed');
        setStatus('error');
      }
    }

    void setup();
    return () => {
      cancelled = true;
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return (
    <div className="maps-canvas">
      <div className="maps-canvas__toolbar">
        <span className="maps-canvas__toolbar-title">Earthquakes</span>
        {status === 'loading' ? (
          <span className="maps-status maps-status--row">
            <Loader2 size={14} className="animate-spin" />
            Loading USGS…
          </span>
        ) : null}
        {status === 'ready' ? (
          <span className="maps-canvas__toolbar-meta">
            {count} events (M≥2.5, past day) · USGS
          </span>
        ) : null}
        {status === 'error' ? (
          <span className="maps-status maps-status--error">
            {error ?? 'USGS feed unavailable'}
          </span>
        ) : null}
      </div>
      <div className="maps-canvas__stage">
        <div ref={containerRef} className="maps-leaflet" />
      </div>
    </div>
  );
}
