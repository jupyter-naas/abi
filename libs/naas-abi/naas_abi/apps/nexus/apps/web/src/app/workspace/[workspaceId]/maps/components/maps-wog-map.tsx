'use client';

import { useEffect, useRef } from 'react';
import type { Map as LeafletMap, Marker } from 'leaflet';

export interface WogMapPin {
  id: string;
  lat: number;
  lng: number;
  label: string;
  address?: string;
  precision?: string;
}

interface MapsWogMapProps {
  pins: WogMapPin[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
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

export function MapsWogMap({ pins, selectedId, onSelect }: MapsWogMapProps) {
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
        const selected = selectedId === pin.id;
        const color = selected ? '#2563eb' : '#0f766e';
        const size = selected ? 16 : 12;
        const icon = L.divIcon({
          className: 'maps-pin-icon',
          html: `<span style="display:block;width:${size}px;height:${size}px;border:2px solid #fff;background:${color};box-shadow:0 1px 4px rgba(0,0,0,.35);border-radius:var(--org-border-radius,0px)"></span>`,
          iconSize: [size, size],
          iconAnchor: [size / 2, size / 2],
        });
        const marker = L.marker([pin.lat, pin.lng], { icon }).addTo(map);
        const meta = [pin.address, pin.precision].filter(Boolean).join(' · ');
        marker.bindPopup(
          `<div class="maps-pin-popup"><strong>${pin.label}</strong>${
            meta ? `<div>${meta}</div>` : ''
          }</div>`,
        );
        marker.on('click', () => onSelect?.(pin.id));
        markersRef.current.push(marker);
        bounds.push([pin.lat, pin.lng]);
      }

      if (selectedId) {
        const selected = withCoords.find((p) => p.id === selectedId);
        if (selected) {
          map.setView([selected.lat, selected.lng], Math.max(map.getZoom(), 4));
        }
      } else if (bounds.length === 1) {
        map.setView(bounds[0], 4);
      } else if (bounds.length > 1) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 5 });
      } else {
        map.setView([20, 0], 2);
      }

      requestAnimationFrame(() => map.invalidateSize());
    }

    void setup();

    return () => {
      cancelled = true;
    };
  }, [pins, selectedId, onSelect]);

  useEffect(() => {
    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  return <div ref={containerRef} className="maps-leaflet maps-wog__map" />;
}
