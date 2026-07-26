'use client';

import { useCallback, useEffect, useState } from 'react';
import { Loader2, Search } from 'lucide-react';
import { authFetch } from '@/stores/auth';
import './maps-components.css';

interface WogOrg {
  slug?: string;
  name?: string;
  label?: string;
  country?: string;
  letter_bucket?: string;
  [key: string]: unknown;
}

export function MapsWog() {
  const [query, setQuery] = useState('');
  const [orgs, setOrgs] = useState<WogOrg[]>([]);
  const [selected, setSelected] = useState<WogOrg | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);

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
  }, [search]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void search(query.trim());
  };

  return (
    <div className="maps-wog">
      <div>
        <h2 style={{ margin: '0 0 0.25rem', fontSize: '1.05rem', fontWeight: 600 }}>
          World Organization Graph
        </h2>
        <p style={{ margin: 0, fontSize: '0.8125rem', color: 'hsl(var(--muted-foreground))' }}>
          Search organizations from the WOG index. Network map viz comes later.
        </p>
      </div>

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
      {!error && source && (
        <p className="maps-status">
          {orgs.length} result{orgs.length === 1 ? '' : 's'}
          {source ? ` · source ${source}` : ''}
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
            const name = org.name || org.label || org.slug || `Org ${idx + 1}`;
            const key = org.slug || `${name}-${idx}`;
            const selectedKey =
              selected?.slug || selected?.name || selected?.label || null;
            const isSelected = selectedKey === (org.slug || name);
            return (
              <button
                key={key}
                type="button"
                role="listitem"
                className={
                  isSelected ? 'maps-wog__row maps-wog__row--selected' : 'maps-wog__row'
                }
                onClick={() => setSelected(org)}
              >
                <span className="maps-wog__row-name">{name}</span>
                <span className="maps-wog__row-meta">
                  {[org.country, org.letter_bucket, org.slug]
                    .filter(Boolean)
                    .join(' · ') || 'Organization'}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {selected && (
        <p className="maps-status">
          Selected: {selected.name || selected.label || selected.slug}. Map network
          stub: selection only for v1.
        </p>
      )}
    </div>
  );
}
