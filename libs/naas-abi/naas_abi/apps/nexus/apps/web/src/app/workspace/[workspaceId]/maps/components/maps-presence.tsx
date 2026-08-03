'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Crosshair, Loader2 } from 'lucide-react';
import dynamic from 'next/dynamic';
import {
  GCP_PRESENCE_PIN,
  MOBILE_GEO_STORAGE_KEY,
} from '../lib/datasets';
import type { PresencePin } from './maps-presence-map';
import './maps-components.css';

const MapsPresenceMap = dynamic(
  () => import('./maps-presence-map').then((m) => m.MapsPresenceMap),
  { ssr: false, loading: () => <div className="maps-leaflet" /> },
);

type GeoStatus = 'idle' | 'pending' | 'granted' | 'denied' | 'unavailable';

interface StoredMobileGeo {
  lat: number;
  lng: number;
  savedAt: string;
  label?: string;
}

function isIPhoneUa(ua: string): boolean {
  return /iPhone/i.test(ua);
}

function isMobileUa(ua: string): boolean {
  return /iPhone|iPad|iPod|Android|Mobile/i.test(ua);
}

function readStoredMobileGeo(): StoredMobileGeo | null {
  try {
    const raw = localStorage.getItem(MOBILE_GEO_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredMobileGeo;
    if (!Number.isFinite(parsed.lat) || !Number.isFinite(parsed.lng)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeStoredMobileGeo(lat: number, lng: number, label: string) {
  const payload: StoredMobileGeo = {
    lat,
    lng,
    label,
    savedAt: new Date().toISOString(),
  };
  try {
    localStorage.setItem(MOBILE_GEO_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Ignore quota / private mode.
  }
}

export function MapsPresence() {
  const [status, setStatus] = useState<GeoStatus>('idle');
  const [devicePin, setDevicePin] = useState<PresencePin | null>(null);
  const [mobilePin, setMobilePin] = useState<PresencePin | null>(null);
  const [error, setError] = useState<string | null>(null);

  const gcpPin: PresencePin = useMemo(
    () => ({
      id: GCP_PRESENCE_PIN.id,
      lat: GCP_PRESENCE_PIN.lat,
      lng: GCP_PRESENCE_PIN.lng,
      label: GCP_PRESENCE_PIN.label,
      kind: 'gcp',
    }),
    [],
  );

  const locate = useCallback(() => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setStatus('unavailable');
      setError('Geolocation is not available in this browser.');
      return;
    }

    setStatus('pending');
    setError(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const ua = navigator.userAgent;
        const onMobile = isMobileUa(ua);
        const onIPhone = isIPhoneUa(ua);

        if (onMobile) {
          const label = onIPhone ? 'This iPhone' : 'This device (mobile)';
          const pin: PresencePin = {
            id: 'device-mobile',
            lat,
            lng,
            label,
            kind: 'mobile',
          };
          setDevicePin(pin);
          setMobilePin(null);
          writeStoredMobileGeo(lat, lng, label);
        } else {
          setDevicePin({
            id: 'device-laptop',
            lat,
            lng,
            label: 'Laptop / This device',
            kind: 'device',
          });
          const stored = readStoredMobileGeo();
          if (stored) {
            setMobilePin({
              id: 'iphone-approx',
              lat: stored.lat,
              lng: stored.lng,
              label: stored.label?.includes('iPhone')
                ? 'iPhone (approximate)'
                : 'Mobile (approximate)',
              kind: 'mobile',
            });
          }
        }
        setStatus('granted');
      },
      (err) => {
        setStatus(err.code === err.PERMISSION_DENIED ? 'denied' : 'unavailable');
        setError(
          err.code === err.PERMISSION_DENIED
            ? 'Location permission denied. GCP pin still shown.'
            : 'Location unavailable. GCP pin still shown.',
        );
        // On desktop without geo, still surface a stored phone pin if any.
        const stored = readStoredMobileGeo();
        if (stored && !isMobileUa(navigator.userAgent)) {
          setMobilePin({
            id: 'iphone-approx',
            lat: stored.lat,
            lng: stored.lng,
            label: 'iPhone (approximate)',
            kind: 'mobile',
          });
        }
      },
      { enableHighAccuracy: false, timeout: 12_000, maximumAge: 60_000 },
    );
  }, []);

  useEffect(() => {
    // Restore stored mobile pin on desktop before geo resolves.
    if (typeof navigator !== 'undefined' && !isMobileUa(navigator.userAgent)) {
      const stored = readStoredMobileGeo();
      if (stored) {
        setMobilePin({
          id: 'iphone-approx',
          lat: stored.lat,
          lng: stored.lng,
          label: 'iPhone (approximate)',
          kind: 'mobile',
        });
      }
    }
    locate();
  }, [locate]);

  const pins = useMemo(() => {
    const list: PresencePin[] = [gcpPin];
    if (devicePin) list.unshift(devicePin);
    if (mobilePin && mobilePin.id !== devicePin?.id) list.push(mobilePin);
    return list;
  }, [devicePin, mobilePin, gcpPin]);

  const legendRows = [
    devicePin
      ? { label: devicePin.label, kind: devicePin.kind }
      : { label: 'This device (awaiting location)', kind: 'unavailable' as const },
    ...(mobilePin && mobilePin.id !== devicePin?.id
      ? [{ label: mobilePin.label, kind: mobilePin.kind }]
      : []),
    { label: gcpPin.label, kind: 'gcp' as const },
  ];

  return (
    <div className="maps-canvas">
      <div className="maps-canvas__toolbar">
        <span className="maps-canvas__toolbar-title">Here</span>
        <span className="maps-canvas__toolbar-meta">
          Presence primer · {pins.length} pin{pins.length === 1 ? '' : 's'}
        </span>
        <button
          type="button"
          className="maps-btn"
          onClick={locate}
          disabled={status === 'pending'}
        >
          {status === 'pending' ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Crosshair size={14} />
          )}
          Locate me
        </button>
        {error && <span className="maps-status maps-status--error">{error}</span>}
        {status === 'pending' && !error && (
          <span className="maps-status">Requesting location…</span>
        )}
      </div>

      <div className="maps-canvas__stage">
        <MapsPresenceMap pins={pins} />
        <aside className="maps-legend" aria-label="Map legend">
          <div className="maps-legend__title">Pins</div>
          {legendRows.map((row) => (
            <div key={row.label} className="maps-legend__row">
              <span
                className={
                  row.kind === 'gcp'
                    ? 'maps-legend__dot maps-legend__dot--gcp'
                    : row.kind === 'mobile'
                      ? 'maps-legend__dot maps-legend__dot--mobile'
                      : row.kind === 'unavailable'
                        ? 'maps-legend__dot maps-legend__dot--muted'
                        : 'maps-legend__dot'
                }
              />
              <span>{row.label}</span>
            </div>
          ))}
        </aside>
      </div>
    </div>
  );
}
