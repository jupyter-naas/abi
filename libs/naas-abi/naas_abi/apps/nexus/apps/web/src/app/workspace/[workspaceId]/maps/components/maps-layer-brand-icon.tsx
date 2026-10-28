'use client';

import { Map } from 'lucide-react';
import { cn } from '@/lib/utils';
import { mapsIconMap } from '../lib/maps-icons';
import { resolveMapsPinImageUrl } from '../lib/maps-pin-image-url';
import type { LayoutEntry } from '../lib/layouts';

export function MapsLayerBrandIcon({
  entry,
  size = 12,
  className,
}: {
  entry: LayoutEntry;
  size?: number;
  className?: string;
}) {
  const logo = resolveMapsPinImageUrl(entry.layerLogoUrl);
  if (logo) {
    return (
      <img
        src={logo}
        alt=""
        width={size}
        height={size}
        className={cn('flex-shrink-0 object-contain', className)}
        aria-hidden
      />
    );
  }
  const Icon = mapsIconMap[entry.icon] || Map;
  return <Icon size={size} className={cn('flex-shrink-0', className)} aria-hidden />;
}
