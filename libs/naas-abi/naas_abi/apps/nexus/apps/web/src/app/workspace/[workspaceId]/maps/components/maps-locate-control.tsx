'use client';

import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { Loader2, LocateFixed } from 'lucide-react';
import type { Map as LeafletMap, Marker } from 'leaflet';

import { createUserLocationMarker, flyMapToUserLocation } from '../lib/leaflet-map';

export interface MapsLocateControlProps {
  mapRef: RefObject<LeafletMap | null>;
  leafletRef: RefObject<typeof import('leaflet') | null>;
  mapReady?: boolean;
  /** Keep auto fit-bounds from overriding this camera move. */
  onLocated?: () => void;
}

const LOCATE_HINT_DEFAULT = 'Go to your current location on the map.';

function locateBlockedHint(reason: string | null): string {
  if (reason === 'Geolocation is not available.') {
    return 'Location is not available in this browser.';
  }
  if (reason === 'Location permission denied.') {
    return 'Location access is blocked. Allow location for this site in your browser settings, then reload.';
  }
  return 'Your location could not be used. Check browser permissions and try again.';
}

export function MapsLocateControl({ mapRef, leafletRef, mapReady = true, onLocated }: MapsLocateControlProps) {
  const markerRef = useRef<Marker | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [locationBlocked, setLocationBlocked] = useState(false);
  const [mount, setMount] = useState<HTMLElement | null>(null);

  useEffect(() => {
    return () => {
      markerRef.current?.remove();
      markerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      setMount(null);
      return;
    }
    const corner = map.getContainer().querySelector('.leaflet-bottom.leaflet-right');
    if (!corner) return;

    const host = document.createElement('div');
    host.className = 'leaflet-control maps-locate-leaflet-control';
    const zoom = corner.querySelector('.leaflet-control-zoom');
    if (zoom) corner.insertBefore(host, zoom);
    else corner.appendChild(host);
    setMount(host);

    return () => {
      host.remove();
      setMount(null);
    };
  }, [mapReady, mapRef]);

  useEffect(() => {
    if (!mapReady || typeof navigator === 'undefined') return;
    if (!navigator.geolocation) {
      setLocationBlocked(true);
      setError('Geolocation is not available.');
      return;
    }
    let cancelled = false;
    const permissions = navigator.permissions;
    if (!permissions?.query) return;

    void permissions
      .query({ name: 'geolocation' })
      .then((status) => {
        if (cancelled) return;
        const sync = () => {
          const denied = status.state === 'denied';
          setLocationBlocked(denied);
          if (denied) setError('Location permission denied.');
          else setError(null);
        };
        sync();
        status.onchange = sync;
      })
      .catch(() => {
        /* Permissions API unsupported; rely on geolocation callback after click */
      });

    return () => {
      cancelled = true;
    };
  }, [mapReady]);

  const locate = useCallback(() => {
    setError(null);
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setLocationBlocked(true);
      setError('Geolocation is not available.');
      return;
    }
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!map || !L || !mapReady) return;

    setPending(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPending(false);
        setLocationBlocked(false);
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        markerRef.current?.remove();
        markerRef.current = createUserLocationMarker(L, map, lat, lng);
        onLocated?.();
        flyMapToUserLocation(map, lat, lng, pos.coords.accuracy);
      },
      (geoError) => {
        setPending(false);
        const denied = geoError.code === geoError.PERMISSION_DENIED;
        if (denied) setLocationBlocked(true);
        setError(denied ? 'Location permission denied.' : 'Could not get your location.');
      },
      { enableHighAccuracy: true, timeout: 12_000, maximumAge: 30_000 },
    );
  }, [leafletRef, mapReady, mapRef, onLocated]);

  if (!mount) return null;

  const blockedHint = locationBlocked ? locateBlockedHint(error) : null;
  const controlDisabled = pending || !mapReady || locationBlocked;

  return createPortal(
    <div
      className={`maps-locate-control-host${locationBlocked ? ' maps-locate-control-host--blocked' : ''}`}
    >
      {blockedHint ? (
        <span id="maps-locate-hint" className="maps-locate-control__hint" role="tooltip">
          {blockedHint}
        </span>
      ) : null}
      <button
        type="button"
        className={`maps-locate-control__btn${locationBlocked ? ' maps-locate-control__btn--blocked' : ''}`}
        aria-label="Go to your location"
        aria-describedby={blockedHint ? 'maps-locate-hint' : undefined}
        title={!locationBlocked ? LOCATE_HINT_DEFAULT : undefined}
        disabled={controlDisabled}
        onClick={locate}
      >
        {pending ? (
          <Loader2 size={18} className="animate-spin" aria-hidden />
        ) : (
          <LocateFixed size={18} aria-hidden />
        )}
      </button>
    </div>,
    mount,
  );
}
