'use client';

import { useEffect, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react';
import { Search, X } from 'lucide-react';

import type { MapsPinMarker } from '../lib/leaflet-map';
import { searchMapPins } from '../lib/maps-pin-search';

export interface MapsPointSearchProps {
  pins: readonly MapsPinMarker[];
  layerTitleForPin?: (pin: MapsPinMarker) => string | undefined;
  onSelectPin: (pin: MapsPinMarker) => void;
  disabled?: boolean;
  searchable?: boolean;
  actions?: ReactNode;
  children?: ReactNode;
  resetKey?: unknown;
  /** Submit opens the record panel instead of a compact results list. */
  recordPanelMode?: boolean;
  query?: string;
  onQueryChange?: (query: string) => void;
  liveEdit?: boolean;
  onSearchSubmit?: (query: string) => void;
  placeholder?: string;
  /** Compact results list (non-inspectable feeds). */
  onResultsOpen?: () => void;
}

export function MapsPointSearch({
  pins,
  layerTitleForPin,
  onSelectPin,
  disabled = false,
  searchable = true,
  actions,
  children,
  resetKey,
  recordPanelMode = false,
  query = '',
  onQueryChange,
  liveEdit = false,
  onSearchSubmit,
  placeholder = 'Search points…',
  onResultsOpen,
}: MapsPointSearchProps) {
  const [draft, setDraft] = useState(query);
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null);

  const showDropdown = !recordPanelMode && submittedQuery !== null;
  const results =
    showDropdown && submittedQuery !== null
      ? searchMapPins(pins, submittedQuery, 12)
      : [];

  const displayValue = recordPanelMode && liveEdit ? query : draft;

  useEffect(() => {
    setSubmittedQuery(null);
    setDraft(query);
  }, [resetKey]);

  useEffect(() => {
    if (liveEdit) setDraft(query);
  }, [liveEdit, query]);

  function clear() {
    setDraft('');
    onQueryChange?.('');
    setSubmittedQuery(null);
  }

  function submitSearch() {
    if (recordPanelMode) {
      const q = draft.trim();
      onQueryChange?.(q);
      onSearchSubmit?.(q);
      return;
    }
    const q = draft.trim();
    if (!q) {
      clear();
      return;
    }
    setSubmittedQuery(q);
    onResultsOpen?.();
  }

  function onFormSubmit(event: FormEvent) {
    event.preventDefault();
    submitSearch();
  }

  function onInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      submitSearch();
    }
    if (event.key === 'Escape') {
      clear();
    }
  }

  if (!searchable && !actions && !children) return null;

  const resultsList = showDropdown ? (
    <div className="maps-point-search__results" role="listbox" aria-label="Search results">
      {results.length ? (
        results.map((pin) => {
          const layer = layerTitleForPin?.(pin);
          const meta = [layer, pin.country, pin.detail?.split('\n')[0]].filter(Boolean).join(' · ');
          return (
            <button
              key={pin.id}
              type="button"
              role="option"
              className="maps-point-search__result"
              onClick={() => {
                onSelectPin(pin);
                setSubmittedQuery(null);
              }}
            >
              <span className="maps-point-search__result-label">{pin.label}</span>
              {meta ? <span className="maps-point-search__result-meta">{meta}</span> : null}
            </button>
          );
        })
      ) : (
        <p className="maps-point-search__empty">No points match &ldquo;{submittedQuery}&rdquo;</p>
      )}
    </div>
  ) : (
    children
  );

  return (
    <div className="maps-point-search">
      <div className="maps-point-search__bar">
        <div className="maps-point-search__main">
          {searchable ? (
            <form className="maps-point-search__field" onSubmit={onFormSubmit}>
              <Search size={15} aria-hidden className="maps-point-search__icon" />
              <input
                type="text"
                inputMode="search"
                enterKeyHint="search"
                value={displayValue}
                disabled={disabled}
                aria-label={recordPanelMode ? 'Search locations' : 'Search map points'}
                aria-expanded={showDropdown}
                placeholder={placeholder}
                autoComplete="off"
                onChange={(event) => {
                  const next = event.target.value;
                  setDraft(next);
                  if (recordPanelMode && liveEdit) onQueryChange?.(next);
                  if (submittedQuery !== null) setSubmittedQuery(null);
                }}
                onKeyDown={onInputKeyDown}
              />
              {displayValue ? (
                <button
                  type="button"
                  className="maps-point-search__clear"
                  aria-label="Clear search"
                  onClick={clear}
                >
                  <X size={14} />
                </button>
              ) : null}
            </form>
          ) : null}
          {resultsList}
        </div>
        {actions}
      </div>
    </div>
  );
}
