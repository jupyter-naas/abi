'use client';

import { useEffect, useRef, useState } from 'react';
import type { Map as LeafletMap, Marker, TileLayer } from 'leaflet';
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

interface FirePin {
  id: string;
  lat: number;
  lng: number;
  label: string;
  detail: string;
}

/**
 * Active wildfires: NASA EONET named open incidents (last 7 days) as clickable
 * pins. Optional NASA FIRMS VIIRS 24h WMS overlay only when FIRMS_MAP_KEY is
 * configured on nexus-web (proxied via /api/maps/firms). Never paints a
 * keyless FIRMS WMS URL (upstream error tiles cover the map).
 */
export function MapsWildfires() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const firmsRef = useRef<TileLayer | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [count, setCount] = useState(0);
  const [firmsEnabled, setFirmsEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function setup() {
      const L = await import('leaflet');
      await import('leaflet/dist/leaflet.css');
      if (cancelled || !containerRef.current) return;

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

      if (!mapRef.current) {
        const map = L.map(containerRef.current, {
          zoomControl: true,
          attributionControl: true,
        });
        L.tileLayer(isMapsDarkMode() ? MAPS_TILE_DARK : MAPS_TILE_LIGHT, {
          attribution: MAPS_TILE_ATTR,
          maxZoom: 18,
        }).addTo(map);

        if (firmsOn) {
          const firms = L.tileLayer.wms(MAPS_PUBLIC_FEEDS.firms, {
            layers: 'fires_viirs_24',
            format: 'image/png',
            transparent: true,
            version: '1.1.1',
            attribution:
              'NASA FIRMS VIIRS 24h · <a href="https://firms.modaps.eosdis.nasa.gov/">FIRMS</a>',
            maxZoom: 18,
          });
          firms.addTo(map);
          firmsRef.current = firms;
        }

        map.setView([20, 0], 2);
        observeMapsLeafletSize(map);
        mapRef.current = map;
      }

      try {
        const res = await fetch(MAPS_PUBLIC_FEEDS.wildfires, {
          signal: AbortSignal.timeout(20000),
        });
        if (!res.ok) throw new Error(`EONET ${res.status}`);
        const data = (await res.json()) as {
          events?: Array<{
            id?: string;
            title?: string;
            link?: string;
            geometry?: Array<{
              date?: string;
              type?: string;
              coordinates?: number[];
              magnitudeValue?: number;
              magnitudeUnit?: string;
            }>;
          }>;
        };

        const pins: FirePin[] = [];
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
          });
        }

        if (cancelled || !mapRef.current) return;
        const map = mapRef.current;
        markersRef.current.forEach((m) => m.remove());
        markersRef.current = [];
        const bounds: [number, number][] = [];

        for (const pin of pins) {
          const icon = L.divIcon({
            className: 'maps-pin-icon',
            html: `<span style="display:block;width:10px;height:10px;border:2px solid #fff;background:#dc2626;box-shadow:0 1px 4px rgba(0,0,0,.35);border-radius:var(--org-border-radius,0px)"></span>`,
            iconSize: [10, 10],
            iconAnchor: [5, 5],
          });
          const marker = L.marker([pin.lat, pin.lng], { icon }).addTo(map);
          const detailHtml = pin.detail
            ? `<div class="maps-pin-popup__meta">${pin.detail}</div>`
            : '';
          marker.bindPopup(
            `<div class="maps-pin-popup"><strong>${pin.label}</strong>${detailHtml}</div>`,
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
        setError(err instanceof Error ? err.message : 'Failed to load EONET feed');
        setStatus('error');
      }
    }

    void setup();
    return () => {
      cancelled = true;
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      firmsRef.current?.remove();
      firmsRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  const readyMeta = firmsEnabled
    ? `VIIRS 24h hotspots (FIRMS) · ${count} named incidents (EONET, 7d)`
    : `${count} named incidents (EONET, 7d) · FIRMS WMS off (no MAP_KEY)`;

  return (
    <div className="maps-canvas">
      <div className="maps-canvas__toolbar">
        <span className="maps-canvas__toolbar-title">Wildfires</span>
        {status === 'loading' ? (
          <span className="maps-status maps-status--row">
            <Loader2 size={14} className="animate-spin" />
            Loading EONET…
          </span>
        ) : null}
        {status === 'ready' ? (
          <span className="maps-canvas__toolbar-meta">{readyMeta}</span>
        ) : null}
        {status === 'error' ? (
          <span className="maps-status maps-status--error">
            {error ?? 'EONET unavailable'}
            {firmsEnabled ? ' · FIRMS WMS may still render' : ''}
          </span>
        ) : null}
      </div>
      <div className="maps-canvas__stage">
        <div ref={containerRef} className="maps-leaflet" />
        {status === 'ready' || status === 'error' ? (
          <div className="maps-legend">
            <div className="maps-legend__title">Legend</div>
            {firmsEnabled ? (
              <div className="maps-legend__row">
                <span
                  className="maps-legend__dot"
                  style={{ background: '#f97316' }}
                />
                <span>NASA FIRMS VIIRS active fires (last 24h)</span>
              </div>
            ) : null}
            <div className="maps-legend__row">
              <span
                className="maps-legend__dot"
                style={{ background: '#dc2626' }}
              />
              <span>EONET named open wildfires (last 7 days)</span>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
