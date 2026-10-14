'use client';

import { useCallback, useState } from 'react';
import { MAPS_PUBLIC_FEEDS } from '../lib/datasets';
import type { MapsPinMarker } from '../lib/leaflet-map';
import { wildfiresFeedLegend } from '../lib/maps-layer-feed-legends';
import { MapsFeedCanvas } from './maps-feed-canvas';

/**
 * NASA EONET named open wildfires (last 7 days) as pins. The standalone canvas
 * can also paint a FIRMS hotspot overlay; the combined map uses these pins.
 */
export async function fetchPins(signal: AbortSignal): Promise<MapsPinMarker[]> {
  const res = await fetch(MAPS_PUBLIC_FEEDS.wildfires, { signal });
  if (!res.ok) throw new Error(`EONET ${res.status}`);
  const data = (await res.json()) as {
    events?: Array<{
      id?: string;
      title?: string;
      geometry?: Array<{
        date?: string;
        type?: string;
        coordinates?: number[];
        magnitudeValue?: number;
        magnitudeUnit?: string;
      }>;
    }>;
  };
  const pins: MapsPinMarker[] = [];
  for (const event of data.events ?? []) {
    const geoms = event.geometry ?? [];
    const point = [...geoms].reverse().find((g) => g.type === 'Point');
    const coords = point?.coordinates;
    if (!coords || coords.length < 2) continue;
    const [lng, lat] = coords;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    const acres =
      point?.magnitudeValue != null && point.magnitudeUnit
        ? `${point.magnitudeValue.toLocaleString()} ${point.magnitudeUnit}`
        : null;
    const when = point?.date
      ? new Date(point.date).toLocaleString(undefined, {
          dateStyle: 'medium',
          timeStyle: 'short',
        })
      : null;
    pins.push({
      id: String(event.id ?? `${lat},${lng}`),
      lat,
      lng,
      label: event.title ?? 'Wildfire',
      detail: [acres, when].filter(Boolean).join(' · '),
      color: '#dc2626',
    });
  }
  return pins;
}

/**
 * Active wildfires: NASA EONET named open incidents (last 7 days) as clickable
 * pins. Optional NASA FIRMS VIIRS 24h WMS overlay when FIRMS_MAP_KEY is
 * configured on nexus-web (proxied via /api/maps/firms).
 */
export function MapsWildfires() {
  const [firmsEnabled, setFirmsEnabled] = useState(false);

  const onMapReady = useCallback(
    ({ L, map }: { L: typeof import('leaflet'); map: import('leaflet').Map }) => {
      let cancelled = false;
      let firmsLayer: ReturnType<typeof L.tileLayer.wms> | null = null;

      void (async () => {
        let firmsOn = false;
        try {
          const firmsStatus = await fetch(`${MAPS_PUBLIC_FEEDS.firms}?status=1`, {
            signal: AbortSignal.timeout(8000),
          });
          if (firmsStatus.ok) {
            const body = (await firmsStatus.json()) as { enabled?: boolean };
            firmsOn = Boolean(body.enabled);
          }
        } catch {
          firmsOn = false;
        }
        if (cancelled) return;
        setFirmsEnabled(firmsOn);
        if (!firmsOn) return;
        firmsLayer = L.tileLayer.wms(MAPS_PUBLIC_FEEDS.firms, {
          layers: 'fires_viirs_24',
          format: 'image/png',
          transparent: true,
          version: '1.1.1',
          attribution:
            'NASA FIRMS VIIRS 24h · <a href="https://firms.modaps.eosdis.nasa.gov/">FIRMS</a>',
          maxZoom: 18,
        });
        firmsLayer.addTo(map);
      })();

      return () => {
        cancelled = true;
        firmsLayer?.remove();
      };
    },
    [],
  );

  return (
    <MapsFeedCanvas
      title="Wildfires"
      loadingLabel="Loading EONET…"
      readyMeta={(count) =>
        firmsEnabled
          ? `VIIRS 24h hotspots (FIRMS) · ${count} named incidents (EONET, 7d)`
          : `${count} named incidents (EONET, 7d) · FIRMS WMS off (no MAP_KEY)`
      }
      sourceHref="https://eonet.gsfc.nasa.gov/"
      sourceLabel="EONET"
      fetchPins={fetchPins}
      fitMaxZoom={5}
      onMapReady={onMapReady}
      legendLayerId="wildfires"
      legend={wildfiresFeedLegend({ firmsEnabled })}
    />
  );
}
