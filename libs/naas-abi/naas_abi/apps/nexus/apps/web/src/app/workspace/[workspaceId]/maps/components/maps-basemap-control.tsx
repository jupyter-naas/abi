'use client';

import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Layers } from 'lucide-react';

import { useAuthedImageUrl } from '@/hooks/use-authed-image-url';
import { basemapsApi } from '../lib/basemaps-api';
import {
  basemapLabel,
  normalizeBasemapId,
  splitBasemapPickerDefs,
  type MapsBasemapDef,
} from '../lib/maps-basemaps';

/** Preview image from the basemap catalog (authenticated, versioned on upload). */
export function MapsBasemapThumb({
  workspaceId,
  def,
  size = 52,
}: {
  workspaceId: string;
  def: Pick<MapsBasemapDef, 'id' | 'previewVersion'>;
  size?: number;
}) {
  const src = useAuthedImageUrl(
    workspaceId && def.previewVersion > 0
      ? basemapsApi.previewUrl(workspaceId, def.id, def.previewVersion)
      : null,
  );
  if (!src) {
    return <span className="maps-basemap-thumb-empty" style={{ width: size, height: size }} />;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element -- blob URL from the authed preview API
    <img src={src} alt="" width={size} height={size} decoding="async" />
  );
}

function BasemapOption({
  def,
  selected,
  workspaceId,
  onPick,
}: {
  def: MapsBasemapDef;
  selected: boolean;
  workspaceId: string;
  onPick: (id: string) => void;
}) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      className="maps-basemap-popover__option"
      onClick={() => onPick(def.id)}
    >
      <span
        className={`maps-basemap-popover__thumb${selected ? ' maps-basemap-popover__thumb--selected' : ''}`}
        aria-hidden
      >
        <MapsBasemapThumb workspaceId={workspaceId} def={def} />
      </span>
      <span className="maps-basemap-popover__option-label">{def.label}</span>
    </button>
  );
}

export interface MapsBasemapControlProps {
  basemapId: string;
  basemapDefs: readonly MapsBasemapDef[];
  workspaceId: string;
  onBasemapChange: (id: string) => void;
}

export function MapsBasemapControl({
  basemapId,
  basemapDefs,
  workspaceId,
  onBasemapChange,
}: MapsBasemapControlProps) {
  const popoverId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<{ left: number; bottom: number } | null>(null);
  const active = normalizeBasemapId(basemapId, basemapDefs);

  useLayoutEffect(() => {
    if (!open) {
      setAnchor(null);
      return;
    }
    const toggle = toggleRef.current;
    if (!toggle) return;

    const syncAnchor = () => {
      const rect = toggle.getBoundingClientRect();
      setAnchor({
        left: Math.round(rect.right + 6),
        bottom: Math.round(window.innerHeight - rect.bottom),
      });
    };

    syncAnchor();
    window.addEventListener('resize', syncAnchor);
    window.addEventListener('scroll', syncAnchor, true);
    return () => {
      window.removeEventListener('resize', syncAnchor);
      window.removeEventListener('scroll', syncAnchor, true);
    };
  }, [open]);

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
      const target = event.target as Node;
      if (rootRef.current?.contains(target) || popoverRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  function pick(id: string) {
    onBasemapChange(normalizeBasemapId(id, basemapDefs));
    setOpen(false);
    toggleRef.current?.focus();
  }

  const { standard, organization, custom } = splitBasemapPickerDefs(basemapDefs);

  const renderColumn = (columnDefs: MapsBasemapDef[], className: string) =>
    columnDefs.length > 0 ? (
      <div className={`maps-basemap-popover__column ${className}`}>
        {columnDefs.map((def) => (
          <BasemapOption
            key={def.id}
            def={def}
            selected={def.id === active}
            workspaceId={workspaceId}
            onPick={pick}
          />
        ))}
      </div>
    ) : null;

  const popover =
    open && anchor ? (
      <div
        ref={popoverRef}
        id={popoverId}
        className="maps-basemap-popover maps-basemap-popover--portal"
        role="dialog"
        aria-label="Map type"
        style={{ left: anchor.left, bottom: anchor.bottom }}
      >
        <div className="maps-basemap-popover__options" role="listbox" aria-label="Basemap">
          {renderColumn(standard, 'maps-basemap-popover__column--standard')}
          {renderColumn(organization, 'maps-basemap-popover__column--group')}
          {renderColumn(custom, 'maps-basemap-popover__column--imported')}
        </div>
      </div>
    ) : null;

  return (
    <>
      <div ref={rootRef} className="maps-basemap-control">
        <button
          ref={toggleRef}
          type="button"
          className="maps-basemap-control__toggle"
          aria-expanded={open}
          aria-controls={open ? popoverId : undefined}
          aria-label={
            open ? 'Close basemap types' : `Basemap: ${basemapLabel(active, basemapDefs)}. Change map type`
          }
          title="Map type"
          onClick={() => setOpen((value) => !value)}
        >
          <Layers size={18} strokeWidth={2} aria-hidden />
        </button>
      </div>
      {popover && typeof document !== 'undefined' ? createPortal(popover, document.body) : null}
    </>
  );
}
