'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { Layers } from 'lucide-react';

import { MAPS_BASEMAPS, basemapLabel, basemapPreviewSrc, normalizeBasemapId } from '../lib/maps-basemaps';

export interface MapsBasemapControlProps {
  basemapId: string;
  onBasemapChange: (id: string) => void;
}

export function MapsBasemapControl({ basemapId, onBasemapChange }: MapsBasemapControlProps) {
  const popoverId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const active = normalizeBasemapId(basemapId);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      const root = rootRef.current;
      if (root && !root.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  function pick(id: string) {
    onBasemapChange(normalizeBasemapId(id));
    setOpen(false);
    toggleRef.current?.focus();
  }

  return (
    <div ref={rootRef} className="maps-basemap-control">
      <button
        ref={toggleRef}
        type="button"
        className="maps-basemap-control__toggle"
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
        aria-label={open ? 'Close basemap types' : `Basemap: ${basemapLabel(active)}. Change map type`}
        title="Map type"
        onClick={() => setOpen((value) => !value)}
      >
        <Layers size={18} strokeWidth={2} aria-hidden />
      </button>

      {open ? (
        <div id={popoverId} className="maps-basemap-popover" role="dialog" aria-label="Map type">
          <p className="maps-basemap-popover__heading">Map type</p>
          <div className="maps-basemap-popover__options" role="listbox" aria-label="Basemap">
            {MAPS_BASEMAPS.map((def) => {
              const selected = def.id === active;
              return (
                <button
                  key={def.id}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className="maps-basemap-popover__option"
                  onClick={() => pick(def.id)}
                >
                  <span
                    className={`maps-basemap-popover__thumb${selected ? ' maps-basemap-popover__thumb--selected' : ''}`}
                    aria-hidden
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element -- static public tile preview */}
                    <img src={basemapPreviewSrc(def.id)} alt="" width={52} height={52} loading="lazy" decoding="async" />
                  </span>
                  <span className="maps-basemap-popover__option-label">{def.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
