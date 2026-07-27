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

interface TempPin {
  lat: number;
  lng: number;
  tempC: number;
  label: string;
}

/** Coarse global sample points (land-biased). Open-Meteo, no API key. */
const TEMP_SAMPLE_POINTS: Array<{ lat: number; lng: number; label: string }> = [
  { lat: 64.15, lng: -21.94, label: 'Reykjavik' },
  { lat: 59.91, lng: 10.75, label: 'Oslo' },
  { lat: 59.33, lng: 18.07, label: 'Stockholm' },
  { lat: 55.76, lng: 37.62, label: 'Moscow' },
  { lat: 52.52, lng: 13.4, label: 'Berlin' },
  { lat: 51.51, lng: -0.13, label: 'London' },
  { lat: 48.86, lng: 2.35, label: 'Paris' },
  { lat: 41.9, lng: 12.5, label: 'Rome' },
  { lat: 40.42, lng: -3.7, label: 'Madrid' },
  { lat: 37.98, lng: 23.73, label: 'Athens' },
  { lat: 30.04, lng: 31.24, label: 'Cairo' },
  { lat: 33.57, lng: -7.59, label: 'Casablanca' },
  { lat: 6.52, lng: 3.38, label: 'Lagos' },
  { lat: -1.29, lng: 36.82, label: 'Nairobi' },
  { lat: -26.2, lng: 28.04, label: 'Johannesburg' },
  { lat: 24.71, lng: 46.68, label: 'Riyadh' },
  { lat: 25.2, lng: 55.27, label: 'Dubai' },
  { lat: 28.61, lng: 77.21, label: 'Delhi' },
  { lat: 19.08, lng: 72.88, label: 'Mumbai' },
  { lat: 13.76, lng: 100.5, label: 'Bangkok' },
  { lat: 1.35, lng: 103.82, label: 'Singapore' },
  { lat: -6.21, lng: 106.85, label: 'Jakarta' },
  { lat: 35.68, lng: 139.69, label: 'Tokyo' },
  { lat: 37.57, lng: 126.98, label: 'Seoul' },
  { lat: 39.9, lng: 116.4, label: 'Beijing' },
  { lat: 31.23, lng: 121.47, label: 'Shanghai' },
  { lat: -33.87, lng: 151.21, label: 'Sydney' },
  { lat: -37.81, lng: 144.96, label: 'Melbourne' },
  { lat: -41.29, lng: 174.78, label: 'Wellington' },
  { lat: 21.31, lng: -157.86, label: 'Honolulu' },
  { lat: 61.22, lng: -149.9, label: 'Anchorage' },
  { lat: 49.28, lng: -123.12, label: 'Vancouver' },
  { lat: 47.61, lng: -122.33, label: 'Seattle' },
  { lat: 37.77, lng: -122.42, label: 'San Francisco' },
  { lat: 34.05, lng: -118.24, label: 'Los Angeles' },
  { lat: 36.17, lng: -115.14, label: 'Las Vegas' },
  { lat: 39.74, lng: -104.99, label: 'Denver' },
  { lat: 41.88, lng: -87.63, label: 'Chicago' },
  { lat: 29.76, lng: -95.37, label: 'Houston' },
  { lat: 25.76, lng: -80.19, label: 'Miami' },
  { lat: 40.71, lng: -74.01, label: 'New York' },
  { lat: 45.5, lng: -73.57, label: 'Montreal' },
  { lat: 19.43, lng: -99.13, label: 'Mexico City' },
  { lat: 9.93, lng: -84.09, label: 'San Jose CR' },
  { lat: 4.71, lng: -74.07, label: 'Bogota' },
  { lat: -12.05, lng: -77.04, label: 'Lima' },
  { lat: -23.55, lng: -46.63, label: 'Sao Paulo' },
  { lat: -34.6, lng: -58.38, label: 'Buenos Aires' },
  { lat: -33.45, lng: -70.67, label: 'Santiago' },
  { lat: 55.75, lng: -3.19, label: 'Edinburgh' },
  { lat: 53.35, lng: -6.26, label: 'Dublin' },
  { lat: 50.45, lng: 30.52, label: 'Kyiv' },
  { lat: 41.01, lng: 28.98, label: 'Istanbul' },
  { lat: 35.69, lng: 51.39, label: 'Tehran' },
  { lat: 33.69, lng: 73.04, label: 'Islamabad' },
  { lat: 23.81, lng: 90.41, label: 'Dhaka' },
  { lat: 14.6, lng: 120.98, label: 'Manila' },
  { lat: -8.65, lng: 115.22, label: 'Denpasar' },
  { lat: -15.78, lng: -47.93, label: 'Brasilia' },
  { lat: 64.84, lng: -147.72, label: 'Fairbanks' },
];

function tempColor(tempC: number): string {
  if (tempC <= -10) return '#1e3a8a';
  if (tempC <= 0) return '#2563eb';
  if (tempC <= 10) return '#38bdf8';
  if (tempC <= 18) return '#4ade80';
  if (tempC <= 26) return '#facc15';
  if (tempC <= 32) return '#f97316';
  return '#dc2626';
}

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    out.push(items.slice(i, i + size));
  }
  return out;
}

/**
 * Current 2m air temperature samples via Open-Meteo (free, no API key).
 * OpenWeather temperature tiles require an app id, so we plot city samples instead.
 */
export function MapsTemperature() {
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
          attribution: `${MAPS_TILE_ATTR} · Open-Meteo`,
          maxZoom: 18,
        }).addTo(map);
        map.setView([20, 0], 2);
        observeMapsLeafletSize(map);
        mapRef.current = map;
      }

      try {
        const pins: TempPin[] = [];
        for (const batch of chunk(TEMP_SAMPLE_POINTS, 40)) {
          const url = new URL(MAPS_PUBLIC_FEEDS.temperature);
          url.searchParams.set(
            'latitude',
            batch.map((p) => p.lat).join(','),
          );
          url.searchParams.set(
            'longitude',
            batch.map((p) => p.lng).join(','),
          );
          url.searchParams.set('current', 'temperature_2m');
          const res = await fetch(url.toString(), {
            signal: AbortSignal.timeout(20000),
          });
          if (!res.ok) throw new Error(`Open-Meteo ${res.status}`);
          const raw = await res.json();
          const rows = Array.isArray(raw) ? raw : [raw];
          for (let i = 0; i < rows.length; i++) {
            const row = rows[i] as {
              latitude?: number;
              longitude?: number;
              current?: { temperature_2m?: number };
            };
            const tempC = row.current?.temperature_2m;
            if (typeof tempC !== 'number' || !Number.isFinite(tempC)) continue;
            const meta = batch[i];
            pins.push({
              lat: row.latitude ?? meta.lat,
              lng: row.longitude ?? meta.lng,
              tempC,
              label: meta.label,
            });
          }
        }

        if (cancelled || !mapRef.current) return;
        const map = mapRef.current;
        markersRef.current.forEach((m) => m.remove());
        markersRef.current = [];

        for (const pin of pins) {
          const color = tempColor(pin.tempC);
          const icon = L.divIcon({
            className: 'maps-pin-icon',
            html: `<span style="display:flex;align-items:center;justify-content:center;min-width:2rem;height:1.25rem;padding:0 0.25rem;border:1px solid #fff;background:${color};color:#111;font-size:0.625rem;font-weight:700;box-shadow:0 1px 4px rgba(0,0,0,.35);border-radius:var(--org-border-radius,0px)">${Math.round(pin.tempC)}°</span>`,
            iconSize: [32, 20],
            iconAnchor: [16, 10],
          });
          const marker = L.marker([pin.lat, pin.lng], { icon }).addTo(map);
          marker.bindPopup(
            `<div class="maps-pin-popup"><strong>${pin.label}</strong><div class="maps-pin-popup__meta">${pin.tempC.toFixed(1)} °C · Open-Meteo</div></div>`,
          );
          markersRef.current.push(marker);
        }

        setCount(pins.length);
        setStatus('ready');
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : 'Failed to load Open-Meteo',
        );
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
        <span className="maps-canvas__toolbar-title">Temperature</span>
        {status === 'loading' ? (
          <span className="maps-status maps-status--row">
            <Loader2 size={14} className="animate-spin" />
            Loading Open-Meteo…
          </span>
        ) : null}
        {status === 'ready' ? (
          <span className="maps-canvas__toolbar-meta">
            {count} city samples · current 2m air temp · Open-Meteo (no key)
          </span>
        ) : null}
        {status === 'error' ? (
          <span className="maps-status maps-status--error">
            {error ?? 'Open-Meteo unavailable'}
          </span>
        ) : null}
      </div>
      <div className="maps-canvas__stage">
        <div ref={containerRef} className="maps-leaflet" />
        {status === 'ready' ? (
          <div className="maps-legend">
            <div className="maps-legend__title">°C</div>
            <div className="maps-legend__row">
              <span className="maps-legend__dot" style={{ background: '#2563eb' }} />
              <span>Cold (≤ 0)</span>
            </div>
            <div className="maps-legend__row">
              <span className="maps-legend__dot" style={{ background: '#4ade80' }} />
              <span>Mild (10-18)</span>
            </div>
            <div className="maps-legend__row">
              <span className="maps-legend__dot" style={{ background: '#f97316' }} />
              <span>Warm (26-32)</span>
            </div>
            <div className="maps-legend__row">
              <span className="maps-legend__dot" style={{ background: '#dc2626' }} />
              <span>Hot (&gt; 32)</span>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
