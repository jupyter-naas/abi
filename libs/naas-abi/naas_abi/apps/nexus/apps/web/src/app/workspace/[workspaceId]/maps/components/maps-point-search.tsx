'use client';

import { useId, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Search, X } from 'lucide-react';

import type { MapsPinMarker } from '../lib/leaflet-map';
import { searchMapPins } from '../lib/maps-pin-search';

export interface MapsPointSearchProps {
  pins: readonly MapsPinMarker[];
  /** Optional subtitle (e.g. layer title on All layers). */
  layerTitleForPin?: (pin: MapsPinMarker) => string | undefined;
  onSelectPin: (pin: MapsPinMarker) => void;
  disabled?: boolean;
}

export function MapsPointSearch({
  pins,
  layerTitleForPin,
  onSelectPin,
  disabled = false,
}: MapsPointSearchProps) {
  const listId = useId();
  const [draft, setDraft] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null);
  const results =
    submittedQuery === null ? [] : searchMapPins(pins, submittedQuery, 12);
  const showResults = submittedQuery !== null;

  function clear() {
    setDraft('');
    setSubmittedQuery(null);
  }

  function submitSearch() {
    const q = draft.trim();
    if (!q) {
      clear();
      return;
    }
    setSubmittedQuery(q);
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

  return (
    <div className="maps-point-search">
      <form className="maps-point-search__field" onSubmit={onFormSubmit}>
        <Search size={15} aria-hidden className="maps-point-search__icon" />
        <input
          type="search"
          value={draft}
          disabled={disabled}
          aria-label="Search map points"
          aria-controls={showResults ? listId : undefined}
          aria-expanded={showResults}
          placeholder="Search points…"
          autoComplete="off"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onInputKeyDown}
        />
        {draft ? (
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
      {showResults ? (
        <div id={listId} className="maps-point-search__results" role="listbox" aria-label="Search results">
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
      ) : null}
    </div>
  );
}
