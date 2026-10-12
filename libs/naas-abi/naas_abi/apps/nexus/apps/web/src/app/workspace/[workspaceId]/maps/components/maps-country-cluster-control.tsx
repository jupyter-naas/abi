'use client';

import { Globe2 } from 'lucide-react';
import type { CountryClusterBy } from '../lib/maps-country-cluster';

export interface MapsCountryClusterControlProps {
  enabled: boolean;
  onToggle: () => void;
  /** Hide when there is nothing to cluster (no country on pins). */
  visible?: boolean;
  /** One badge per layer or per layer feed (shown while grouping is on). */
  groupBy?: CountryClusterBy;
  onGroupByChange?: (by: CountryClusterBy) => void;
}

const GROUP_BY: { value: CountryClusterBy; label: string; title: string }[] = [
  { value: 'layer', label: 'Layer', title: 'One count per layer in each country' },
  { value: 'feed', label: 'Feed', title: 'One count per layer feed in each country (each site once)' },
];

export function MapsCountryClusterControl({
  enabled,
  onToggle,
  visible = true,
  groupBy = 'layer',
  onGroupByChange,
}: MapsCountryClusterControlProps) {
  if (!visible) return null;

  return (
    <span className="maps-cluster-control">
      <button
        type="button"
        className="maps-toolbar-icon-btn maps-canvas__toolbar-cluster"
        aria-pressed={enabled}
        aria-label={
          enabled
            ? 'Country grouping on. Click to show every location.'
            : 'Country grouping off. Click to group locations by country when zoomed out.'
        }
        title={enabled ? 'Ungroup by country' : 'Group by country'}
        onClick={onToggle}
        data-testid="maps-toolbar-country-cluster"
      >
        <Globe2 size={16} strokeWidth={2} aria-hidden />
      </button>
      {enabled && onGroupByChange ? (
        <span className="maps-cluster-control__by" role="radiogroup" aria-label="Group by">
          {GROUP_BY.map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={groupBy === option.value}
              title={option.title}
              className={
                groupBy === option.value
                  ? 'maps-cluster-control__option maps-cluster-control__option--active'
                  : 'maps-cluster-control__option'
              }
              onClick={() => onGroupByChange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </span>
      ) : null}
    </span>
  );
}
