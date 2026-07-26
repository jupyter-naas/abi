'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { Loader2, Search } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import type { WogMapPin } from './maps-wog-map';
import './maps-components.css';

const MapsWogMap = dynamic(
  () => import('./maps-wog-map').then((m) => m.MapsWogMap),
  { ssr: false, loading: () => <div className="maps-leaflet maps-wog__map" /> },
);

interface WogOrg {
  slug?: string;
  name?: string;
  label?: string;
  display_name?: string;
  country?: string;
  letter_bucket?: string;
  [key: string]: unknown;
}

interface LocatedOrg {
  slug?: string;
  label?: string;
  lat?: number;
  lng?: number;
  address?: string;
  precision?: string;
}

function orgName(org: WogOrg, fallback: string): string {
  return org.name || org.label || org.display_name || org.slug || fallback;
}

export function MapsWog() {
  const [query, setQuery] = useState('');
  const [orgs, setOrgs] = useState<WogOrg[]>([]);
  const [pins, setPins] = useState<WogMapPin[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [locatedTotal, setLocatedTotal] = useState(0);

  const loadLocations = useCallback(async () => {
    try {
      const res = await authFetch('/api/wog/locations?limit=5000');
      if (!res.ok) {
        setPins([]);
        setLocatedTotal(0);
        return;
      }
      const data = (await res.json()) as {
        organizations?: LocatedOrg[];
        total?: number;
      };
      const nextPins: WogMapPin[] = (data.organizations || [])
        .filter(
          (org) =>
            org.slug &&
            Number.isFinite(org.lat) &&
            Number.isFinite(org.lng),
        )
        .map((org) => ({
          id: String(org.slug),
          lat: Number(org.lat),
          lng: Number(org.lng),
          label: org.label || String(org.slug),
          address: org.address,
          precision: org.precision,
        }));
      setPins(nextPins);
      setLocatedTotal(data.total ?? nextPins.length);
    } catch {
      setPins([]);
      setLocatedTotal(0);
    }
  }, []);

  const search = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(
        `/api/wog/organizations?q=${encodeURIComponent(q)}&limit=40`,
      );
      if (!res.ok) {
        setOrgs([]);
        setSource(null);
        setError(
          res.status === 404
            ? 'WOG index is not available yet.'
            : `WOG API returned ${res.status}.`,
        );
        return;
      }
      const data = (await res.json()) as {
        organizations?: WogOrg[];
        source?: string;
        count?: number;
      };
      setOrgs(Array.isArray(data.organizations) ? data.organizations : []);
      setSource(data.source ?? null);
    } catch {
      setOrgs([]);
      setSource(null);
      setError('Could not reach the WOG API. Maps still works; try again later.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void search('');
    void loadLocations();
  }, [search, loadLocations]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void search(query.trim());
  };

  const selectedPin = useMemo(
    () => pins.find((pin) => pin.id === selectedSlug) || null,
    [pins, selectedSlug],
  );

  return (
    <div className="maps-wog">
      <div>
        <h2 style={{ margin: '0 0 0.25rem', fontSize: '1.05rem', fontWeight: 600 }}>
          World Organization Graph
        </h2>
        <p style={{ margin: 0, fontSize: '0.8125rem', color: 'hsl(var(--muted-foreground))' }}>
          Search the WOG index and plot organizations that have geocoded
          locations.json points.
        </p>
      </div>

      <MapsWogMap
        pins={pins}
        selectedId={selectedSlug}
        onSelect={(id) => setSelectedSlug(id)}
      />

      <form className="maps-wog__search" onSubmit={onSubmit}>
        <input
          className="maps-wog__input"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search organizations…"
          aria-label="Search organizations"
        />
        <button type="submit" className="maps-btn" disabled={loading}>
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          Search
        </button>
      </form>

      {error && <p className="maps-status maps-status--error">{error}</p>}
      {!error && (
        <p className="maps-status">
          {locatedTotal} located on map
          {source ? ` · search ${orgs.length} · source ${source}` : ''}
        </p>
      )}

      {orgs.length === 0 && !loading ? (
        <div className="maps-empty">
          <h3>No organizations</h3>
          <p>
            The WOG API is empty or unreachable. Presence map still works from the
            library. Sync the WOG referential when the API is available.
          </p>
        </div>
      ) : (
        <div className="maps-wog__list" role="list">
          {orgs.map((org, idx) => {
            const name = orgName(org, `Org ${idx + 1}`);
            const key = org.slug || `${name}-${idx}`;
            const slug = org.slug || null;
            const isSelected = selectedSlug != null && selectedSlug === slug;
            const hasPin = slug ? pins.some((pin) => pin.id === slug) : false;
            return (
              <button
                key={key}
                type="button"
                role="listitem"
                className={
                  isSelected ? 'maps-wog__row maps-wog__row--selected' : 'maps-wog__row'
                }
                onClick={() => slug && setSelectedSlug(slug)}
              >
                <span className="maps-wog__row-name">{name}</span>
                <span className="maps-wog__row-meta">
                  {[
                    hasPin ? 'on map' : 'no coords',
                    org.country,
                    org.letter_bucket,
                    org.slug,
                  ]
                    .filter(Boolean)
                    .join(' · ') || 'Organization'}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {selectedPin && (
        <p className="maps-status">
          Selected: {selectedPin.label}
          {selectedPin.address ? ` · ${selectedPin.address}` : ''}
        </p>
      )}
    </div>
  );
}
