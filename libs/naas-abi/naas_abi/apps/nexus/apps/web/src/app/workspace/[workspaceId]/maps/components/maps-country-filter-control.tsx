'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Filter, Search } from 'lucide-react';

export type MapsCountryFilter =
  | { mode: 'all' }
  | { mode: 'none' }
  | { mode: 'some'; countries: ReadonlySet<string> };

export function mapsCountryFilterAll(): MapsCountryFilter {
  return { mode: 'all' };
}

export function isCountryFilterActive(filter: MapsCountryFilter): boolean {
  return filter.mode !== 'all';
}

export function mapsCountryFilterLabel(
  selected: MapsCountryFilter,
  allCount: number,
): string {
  if (selected.mode === 'all') return 'All countries';
  if (selected.mode === 'none') return 'No countries';
  if (selected.countries.size === 1) return [...selected.countries][0];
  if (selected.countries.size === allCount) return 'All countries';
  return `${selected.countries.size} countries`;
}

export function pinMatchesCountryFilter(
  country: string | undefined,
  filter: MapsCountryFilter,
): boolean {
  if (filter.mode === 'all') return true;
  if (filter.mode === 'none') return false;
  if (!country) return false;
  return filter.countries.has(country);
}

export interface MapsCountryFilterControlProps {
  countries: readonly string[];
  selected: MapsCountryFilter;
  onChange: (next: MapsCountryFilter) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MapsCountryFilterControl({
  countries,
  selected,
  onChange,
  open,
  onOpenChange,
}: MapsCountryFilterControlProps) {
  const rootRef = useRef<HTMLSpanElement>(null);
  const panelId = useId();
  const [draft, setDraft] = useState('');

  const filtered = useMemo(() => {
    const q = draft.trim().toLowerCase();
    if (!q) return countries;
    return countries.filter((c) => c.toLowerCase().includes(q));
  }, [countries, draft]);

  useEffect(() => {
    if (!open) setDraft('');
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) onOpenChange(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onOpenChange(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [open, onOpenChange]);

  function isChecked(country: string): boolean {
    if (selected.mode === 'all') return true;
    if (selected.mode === 'none') return false;
    return selected.countries.has(country);
  }

  function toggleCountry(country: string) {
    const all = new Set(countries);
    if (selected.mode === 'all') {
      onChange({ mode: 'some', countries: new Set([country]) });
      return;
    }
    if (selected.mode === 'none') {
      onChange({ mode: 'some', countries: new Set([country]) });
      return;
    }
    const next = new Set(selected.countries);
    if (next.has(country)) {
      next.delete(country);
      onChange(next.size === 0 ? { mode: 'none' } : { mode: 'some', countries: next });
      return;
    }
    next.add(country);
    onChange(next.size === all.size ? { mode: 'all' } : { mode: 'some', countries: next });
  }

  return (
    <span ref={rootRef} className="maps-country-filter">
      <button
        type="button"
        className="maps-record-toggle maps-country-filter__toggle"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => onOpenChange(!open)}
      >
        <Filter size={15} aria-hidden />
        {mapsCountryFilterLabel(selected, countries.length)}
      </button>
      {open ? (
        <div
          id={panelId}
          className="maps-country-filter__panel"
          role="dialog"
          aria-label="Filter by country"
          onMouseDown={(event) => event.stopPropagation()}
        >
          <label className="maps-country-filter__search">
            <Search size={14} aria-hidden />
            <input
              type="text"
              value={draft}
              placeholder="Search countries…"
              aria-label="Search countries"
              autoComplete="off"
              onChange={(event) => setDraft(event.target.value)}
            />
          </label>
          <div className="maps-country-filter__actions">
            <button
              type="button"
              className="maps-country-filter__reset"
              onClick={() => onChange({ mode: 'all' })}
            >
              Select all
            </button>
            <button
              type="button"
              className="maps-country-filter__reset"
              onClick={() => onChange({ mode: 'none' })}
            >
              Deselect all
            </button>
          </div>
          <ul className="maps-country-filter__list">
            {filtered.map((country) => (
              <li key={country}>
                <label className="maps-country-filter__option">
                  <input
                    type="checkbox"
                    checked={isChecked(country)}
                    onChange={() => toggleCountry(country)}
                  />
                  <span>{country}</span>
                </label>
              </li>
            ))}
            {!filtered.length ? (
              <li className="maps-country-filter__empty">No country matches</li>
            ) : null}
          </ul>
        </div>
      ) : null}
    </span>
  );

}
