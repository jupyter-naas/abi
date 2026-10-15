'use client';

import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Filter, Search } from 'lucide-react';

export type MapsRegionFilter =
  | { mode: 'all' }
  | { mode: 'none' }
  | { mode: 'some'; regions: ReadonlySet<string> };

export function mapsRegionFilterAll(): MapsRegionFilter {
  return { mode: 'all' };
}

export function isRegionFilterActive(filter: MapsRegionFilter): boolean {
  return filter.mode !== 'all';
}

export function mapsRegionFilterLabel(
  selected: MapsRegionFilter,
  allCount: number,
): string {
  if (selected.mode === 'all') return 'All regions';
  if (selected.mode === 'none') return 'No regions';
  if (selected.regions.size === 1) return [...selected.regions][0];
  if (selected.regions.size === allCount) return 'All regions';
  return `${selected.regions.size} regions`;
}

export interface MapsRegionFilterControlProps {
  regions: readonly string[];
  selected: MapsRegionFilter;
  onChange: (next: MapsRegionFilter) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Continent multi-select (default label: All regions). */
export function MapsRegionFilterControl({
  regions,
  selected,
  onChange,
  open,
  onOpenChange,
}: MapsRegionFilterControlProps) {
  const rootRef = useRef<HTMLSpanElement>(null);
  const panelId = useId();
  const [draft, setDraft] = useState('');

  const filtered = useMemo(() => {
    const q = draft.trim().toLowerCase();
    if (!q) return regions;
    return regions.filter((r) => r.toLowerCase().includes(q));
  }, [regions, draft]);

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

  function isChecked(region: string): boolean {
    if (selected.mode === 'all') return true;
    if (selected.mode === 'none') return false;
    return selected.regions.has(region);
  }

  function toggleRegion(region: string) {
    if (selected.mode === 'all') {
      onChange({ mode: 'some', regions: new Set([region]) });
      return;
    }
    if (selected.mode === 'none') {
      onChange({ mode: 'some', regions: new Set([region]) });
      return;
    }
    const all = new Set(regions);
    const next = new Set(selected.regions);
    if (next.has(region)) {
      next.delete(region);
      onChange(next.size === 0 ? { mode: 'none' } : { mode: 'some', regions: next });
      return;
    }
    next.add(region);
    onChange(next.size === all.size ? { mode: 'all' } : { mode: 'some', regions: next });
  }

  return (
    <span ref={rootRef} className="maps-region-filter">
      <button
        type="button"
        className="maps-record-toggle maps-region-filter__toggle"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => onOpenChange(!open)}
      >
        <Filter size={15} aria-hidden />
        {mapsRegionFilterLabel(selected, regions.length)}
      </button>
      {open ? (
        <div
          id={panelId}
          className="maps-region-filter__panel"
          role="dialog"
          aria-label="Filter by region"
          onMouseDown={(event) => event.stopPropagation()}
        >
          <label className="maps-region-filter__search">
            <Search size={14} aria-hidden />
            <input
              type="text"
              value={draft}
              placeholder="Search regions…"
              aria-label="Search regions"
              autoComplete="off"
              onChange={(event) => setDraft(event.target.value)}
            />
          </label>
          <div className="maps-region-filter__actions">
            <button
              type="button"
              className="maps-region-filter__reset"
              onClick={() => onChange({ mode: 'all' })}
            >
              Select all
            </button>
            <button
              type="button"
              className="maps-region-filter__reset"
              onClick={() => onChange({ mode: 'none' })}
            >
              Deselect all
            </button>
          </div>
          <ul className="maps-region-filter__list">
            {filtered.map((region) => (
              <li key={region}>
                <label className="maps-region-filter__option">
                  <input
                    type="checkbox"
                    checked={isChecked(region)}
                    onChange={() => toggleRegion(region)}
                  />
                  <span>{region}</span>
                </label>
              </li>
            ))}
            {!filtered.length ? (
              <li className="maps-region-filter__empty">No region matches</li>
            ) : null}
          </ul>
        </div>
      ) : null}
    </span>
  );
}
