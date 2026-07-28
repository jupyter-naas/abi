'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Map as LeafletMap, Marker } from 'leaflet';
import { ExternalLink, Loader2 } from 'lucide-react';
import {
  addMapsPinMarkers,
  clearMapsMarkers,
  createMapsLeaflet,
  destroyMapsLeaflet,
  fitMapsBounds,
  type MapsPinMarker,
} from '../lib/leaflet-map';
import './maps-components.css';

export type MapsFeedStatus = 'loading' | 'ready' | 'error' | 'empty';

export interface MapsFeedCanvasProps {
  title: string;
  loadingLabel: string;
  /** Shown when status is ready and count > 0. */
  readyMeta: (count: number) => string;
  emptyTitle?: string;
  emptyBody?: string;
  sourceHref?: string;
  sourceLabel?: string;
  fetchPins: (signal: AbortSignal) => Promise<MapsPinMarker[]>;
  fitMaxZoom?: number;
  legend?: ReactNode;
  /** Optional refresh interval in ms (e.g. flights). */
  refreshMs?: number;
}

/**
 * Shared pin-map canvas used by Public situation-awareness layers.
 * Keeps Leaflet bootstrap / marker lifecycle in one place.
 */
export function MapsFeedCanvas({
  title,
  loadingLabel,
  readyMeta,
  emptyTitle = 'No data',
  emptyBody = 'This feed returned no mappable points right now.',
  sourceHref,
  sourceLabel = 'Source',
  fetchPins,
  fitMaxZoom = 5,
  legend,
  refreshMs,
}: MapsFeedCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const leafletRef = useRef<typeof import('leaflet') | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const [status, setStatus] = useState<MapsFeedStatus>('loading');
  const [count, setCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function loadPins(isRefresh: boolean) {
      if (!containerRef.current) return;
      if (!isRefresh) {
        setStatus('loading');
        setError(null);
      }

      try {
        if (!mapRef.current) {
          const { L, map } = await createMapsLeaflet(containerRef.current);
          if (cancelled) {
            map.remove();
            return;
          }
          leafletRef.current = L;
          mapRef.current = map;
        }

        const L = leafletRef.current ?? (await import('leaflet'));
        const pins = await fetchPins(AbortSignal.timeout(25000));
        if (cancelled || !mapRef.current) return;

        clearMapsMarkers(markersRef.current);
        const bounds = addMapsPinMarkers(
          L,
          mapRef.current,
          pins,
          markersRef.current,
        );
        if (!isRefresh) {
          fitMapsBounds(mapRef.current, bounds, { maxZoom: fitMaxZoom });
        }

        setCount(pins.length);
        setStatus(pins.length === 0 ? 'empty' : 'ready');
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load feed');
        setStatus('error');
      }
    }

    void loadPins(false);
    if (refreshMs && refreshMs > 0) {
      timer = setInterval(() => {
        void loadPins(true);
      }, refreshMs);
    }

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      destroyMapsLeaflet(mapRef.current, markersRef.current);
      mapRef.current = null;
      leafletRef.current = null;
    };
    // fetchPins identity is stable in callers (module-level async functions).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshMs, fitMaxZoom]);

  return (
    <div className="maps-canvas">
      <div className="maps-canvas__toolbar">
        <span className="maps-canvas__toolbar-title">{title}</span>
        {status === 'loading' ? (
          <span className="maps-status maps-status--row">
            <Loader2 size={14} className="animate-spin" />
            {loadingLabel}
          </span>
        ) : null}
        {status === 'ready' ? (
          <span className="maps-canvas__toolbar-meta">{readyMeta(count)}</span>
        ) : null}
        {status === 'empty' ? (
          <span className="maps-canvas__toolbar-meta">{emptyTitle}</span>
        ) : null}
        {status === 'error' ? (
          <span className="maps-status maps-status--error">
            {error ?? 'Feed unavailable'}
          </span>
        ) : null}
      </div>
      <div className="maps-canvas__stage">
        <div ref={containerRef} className="maps-leaflet" />
        {status === 'empty' || status === 'error' ? (
          <div className="maps-empty-overlay">
            <h3>{status === 'error' ? 'Feed unavailable' : emptyTitle}</h3>
            <p>{status === 'error' ? (error ?? emptyBody) : emptyBody}</p>
            {sourceHref ? (
              <a
                className="maps-btn"
                href={sourceHref}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={12} />
                {sourceLabel}
              </a>
            ) : null}
          </div>
        ) : null}
        {legend && (status === 'ready' || status === 'empty') ? legend : null}
      </div>
    </div>
  );
}
