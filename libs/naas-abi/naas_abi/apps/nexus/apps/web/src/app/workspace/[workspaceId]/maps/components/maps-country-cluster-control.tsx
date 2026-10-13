'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { Globe2 } from 'lucide-react';
import type { MapsGroupBy } from '../lib/maps-country-cluster';

export interface MapsCountryClusterControlProps {
  groupBy: MapsGroupBy;
  onGroupByChange: (by: MapsGroupBy) => void;
  /** Hide when there is nothing to group (no country on pins). */
  visible?: boolean;
}

const GROUP_BY: { value: MapsGroupBy; label: string; hint: string }[] = [
  { value: 'feed', label: 'Layers feed', hint: 'One count per feed (each site once)' },
  { value: 'layer', label: 'Layers', hint: 'One count per layer' },
  { value: 'off', label: 'Off', hint: 'Every location, no grouping' },
];

/** Toolbar "Group" button; its panel picks what to count (by country at low zoom). */
export function MapsCountryClusterControl({
  groupBy,
  onGroupByChange,
  visible = true,
}: MapsCountryClusterControlProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!visible) return null;
  const on = groupBy !== 'off';

  return (
    <span ref={rootRef} className="maps-group-control">
      <button
        type="button"
        className="maps-toolbar-icon-btn maps-canvas__toolbar-cluster"
        aria-pressed={on}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={`Group: ${GROUP_BY.find((o) => o.value === groupBy)?.label ?? 'Off'}`}
        title="Group"
        onClick={() => setOpen((value) => !value)}
        data-testid="maps-toolbar-country-cluster"
      >
        <Globe2 size={16} strokeWidth={2} aria-hidden />
      </button>
      {open ? (
        <div id={panelId} className="maps-group-panel" role="dialog" aria-label="Group">
          <fieldset className="maps-group-panel__section">
            <legend className="maps-group-panel__title">Group</legend>
            {GROUP_BY.map((option) => (
              <label key={option.value} className="maps-group-panel__option" title={option.hint}>
                <input
                  type="radio"
                  name={`${panelId}-by`}
                  checked={groupBy === option.value}
                  onChange={() => onGroupByChange(option.value)}
                />
                <span>{option.label}</span>
                {option.value === 'feed' ? <span className="maps-group-panel__default">default</span> : null}
              </label>
            ))}
          </fieldset>
        </div>
      ) : null}
    </span>
  );
}
