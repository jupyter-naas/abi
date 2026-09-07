'use client';

import { useEffect, useRef } from 'react';
import type { Map as LeafletMap, Marker } from 'leaflet';
import { observeMapsLeafletSize } from '../lib/leaflet-map';

export interface PresencePin {
  id: string;
  lat: number;
  lng: number;
  label: string;
  kind: 'device' | 'mobile' | 'gcp' | 'unavailable';
}

interface MapsPresenceMapProps {
  pins: PresencePin[];
}

const TILE_LIGHT =
  'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
const TILE_DARK =
  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const TILE_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

function isDarkMode(): boolean {
  if (typeof document === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
}

function pinColor(kind: PresencePin['kind']): string {
  if (kind === 'gcp') return '#3b82f6';
  if (kind === 'mobile') return '#a855f7';
  if (kind === 'unavailable') return '#94a3b8';
  return '#22c55e';
}

export function MapsPresenceMap({ pins }: MapsPresenceMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Marker[]>([]);

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
        L.tileLayer(isDarkMode() ? TILE_DARK : TILE_LIGHT, {
          attribution: TILE_ATTR,
          maxZoom: 18,
        }).addTo(map);
        observeMapsLeafletSize(map);
        mapRef.current = map;
      }

      const map = mapRef.current;
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];

      const withCoords = pins.filter(
        (p) => Number.isFinite(p.lat) && Number.isFinite(p.lng),
      );

      const bounds: [number, number][] = [];
      for (const pin of withCoords) {
        const color = pinColor(pin.kind);
        const icon = L.divIcon({
          className: 'maps-pin-icon',
          html: `<span style="display:block;width:14px;height:14px;border:2px solid #fff;background:${color};box-shadow:0 1px 4px rgba(0,0,0,.35);border-radius:var(--org-border-radius,0px)"></span>`,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        });
        const marker = L.marker([pin.lat, pin.lng], { icon }).addTo(map);
        marker.bindPopup(
          `<div class="maps-pin-popup"><strong>${pin.label}</strong>${pin.lat.toFixed(4)}, ${pin.lng.toFixed(4)}</div>`,
        );
        markersRef.current.push(marker);
        bounds.push([pin.lat, pin.lng]);
      }

      if (bounds.length === 1) {
        map.setView(bounds[0], 5);
      } else if (bounds.length > 1) {
        map.fitBounds(bounds, { padding: [48, 48], maxZoom: 6 });
      } else {
        map.setView([41.2619, -95.8608], 3);
      }
    }

    void setup();

    return () => {
      cancelled = true;
    };
  }, [pins]);

  useEffect(() => {
    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  return <div ref={containerRef} className="maps-leaflet" aria-label="Presence map" />;
}
