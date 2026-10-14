'use client';

import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { temperatureFeedLegend } from '../lib/maps-layer-feed-legends';
import { MapsFeedCanvas } from './maps-feed-canvas';

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

async function loadTemperatureSamples(signal: AbortSignal): Promise<TempPin[]> {
  const pins: TempPin[] = [];
  for (const batch of chunk(TEMP_SAMPLE_POINTS, 40)) {
    const url = new URL(MAPS_PUBLIC_FEEDS.temperature);
    url.searchParams.set('latitude', batch.map((p) => p.lat).join(','));
    url.searchParams.set('longitude', batch.map((p) => p.lng).join(','));
    url.searchParams.set('current', 'temperature_2m');
    const res = await fetch(url.toString(), { signal });
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
  return pins;
}

/** City temperature samples as pins for the combined map. */
export async function fetchPins(signal: AbortSignal): Promise<MapsPinMarker[]> {
  const samples = await loadTemperatureSamples(signal);
  return samples.map((pin) => ({
    id: pin.label,
    lat: pin.lat,
    lng: pin.lng,
    label: `${pin.label} · ${pin.tempC.toFixed(1)} °C`,
    detail: 'Open-Meteo 2m air temperature',
    color: tempColor(pin.tempC),
  }));
}

/**
 * Current 2m air temperature samples via Open-Meteo (free, no API key).
 */
export function MapsTemperature() {
  return (
    <MapsFeedCanvas
      title="Temperature"
      loadingLabel="Loading Open-Meteo…"
      readyMeta={(n) => `${n} city samples · current 2m air temp · Open-Meteo (no key)`}
      sourceHref="https://open-meteo.com/"
      sourceLabel="Open-Meteo"
      fetchPins={fetchPins}
      fitMaxZoom={4}
      legendLayerId="temperature"
      legend={temperatureFeedLegend()}
    />
  );
}
