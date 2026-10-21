'use client';

import type { MapRegionDefinition, RegionFeedFacilityCount } from '../lib/maps-map-regions';

export interface MapsRegionLabelsProps {
  regions: readonly MapRegionDefinition[];
  countsByFeed: ReadonlyMap<string, readonly RegionFeedFacilityCount[]>;
  /** When more than one feed is on the map, show a line per feed. */
  multiFeed: boolean;
  countLabel?: string;
  onSelectRegion?: (regionId: string) => void;
}

function pluralCountLabel(base: string): string {
  if (base.endsWith('s')) return base;
  if (base.endsWith('y') && base.length > 1) {
    const beforeY = base.charAt(base.length - 2).toLowerCase();
    if (!'aeiou'.includes(beforeY)) {
      return `${base.slice(0, -1)}ies`;
    }
  }
  return `${base}s`;
}

function facilityUnit(count: number, countLabel: string): string {
  const base = countLabel.trim() || 'facility';
  if (count === 1) return base;
  return pluralCountLabel(base);
}

/** Region name + facility counts anchored on the map (feed-driven overlay). */
export function MapsRegionLabels({
  regions,
  countsByFeed,
  multiFeed,
  countLabel = 'facility',
  onSelectRegion,
}: MapsRegionLabelsProps) {
  return (
    <div className="maps-region-labels" aria-hidden={!onSelectRegion}>
      {regions.map((region) => {
        const lines = countsByFeed.get(region.id) ?? [];
        const total = lines.reduce((sum, row) => sum + row.count, 0);
        const nameLines = region.name.split('\n');
        const statLines =
          lines.length === 0
            ? [{ key: 'empty', text: `0 ${facilityUnit(0, countLabel)}` }]
            : multiFeed
              ? lines.map((row) => ({
                  key: row.feedId,
                  text: `${row.label}: ${row.count} ${facilityUnit(row.count, countLabel)}`,
                }))
              : [
                  {
                    key: lines[0]?.feedId ?? 'total',
                    text: `${total} ${facilityUnit(total, countLabel)}`,
                  },
                ];
        const ariaStats = statLines.map((line) => line.text).join(', ');
        return (
          <button
            key={region.id}
            type="button"
            className="maps-region-label"
            style={{
              left: `${region.labelX * 100}%`,
              top: `${region.labelY * 100}%`,
              ['--maps-region-color' as string]: region.color,
            }}
            onClick={onSelectRegion ? () => onSelectRegion(region.id) : undefined}
            tabIndex={onSelectRegion ? 0 : -1}
            aria-label={`${region.name}, ${ariaStats}`}
          >
            <div className="maps-region-label__name">
              {nameLines.map((line, index) => (
                <span key={index}>
                  {line}
                  {index < nameLines.length - 1 ? <br /> : null}
                </span>
              ))}
            </div>
            <div className="maps-region-label__stats">
              {statLines.map((line, index) => (
                <span key={line.key}>
                  {index > 0 ? <br /> : null}
                  {line.text}
                </span>
              ))}
            </div>
          </button>
        );
      })}
    </div>
  );
}
