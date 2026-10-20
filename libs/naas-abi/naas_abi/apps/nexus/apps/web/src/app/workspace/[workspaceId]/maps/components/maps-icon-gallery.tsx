'use client';

import { cn } from '@/lib/utils';
import { mapsIconMap } from '../lib/maps-icons';

const ICON_KEYS = Object.keys(mapsIconMap).sort();

export function MapsIconGallery({
  value,
  onChange,
  'aria-label': ariaLabel = 'Layer icon',
}: {
  value: string;
  onChange: (iconKey: string) => void;
  'aria-label'?: string;
}) {
  return (
    <div className="maps-icon-gallery" role="listbox" aria-label={ariaLabel}>
      {ICON_KEYS.map((key) => {
        const Icon = mapsIconMap[key];
        const selected = value === key;
        return (
          <button
            key={key}
            type="button"
            role="option"
            aria-selected={selected}
            aria-label={key}
            title={key}
            className={cn('maps-icon-gallery__btn', selected && 'maps-icon-gallery__btn--selected')}
            onClick={() => onChange(key)}
          >
            <Icon size={16} aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
