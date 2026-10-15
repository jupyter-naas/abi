'use client';

import type { CSSProperties } from 'react';
import { cn } from '@/lib/utils';
import { DEFAULT_FRAMING, type BackgroundFraming } from '@/lib/home-background';
import { HERO_OVERLAY, deskFallbackColor } from '../home-desk';

/**
 * The Home desk wallpaper, drawn the same way on the desk and in the Edit
 * background image preview so what is framed there is what the desk shows:
 * the image covers the frame, its focal point (x%, y%) is kept in view, and
 * it is scaled by `zoom` around that point. The overlay keeps desk icons legible.
 */
export function DeskWallpaper({
  imageUrl,
  framing = DEFAULT_FRAMING,
  fallbackColor,
  className,
}: {
  imageUrl?: string;
  framing?: BackgroundFraming;
  fallbackColor?: string;
  className?: string;
}) {
  const focal = `${framing.x}% ${framing.y}%`;
  const imageStyle: CSSProperties = {
    backgroundImage: imageUrl ? `url(${JSON.stringify(imageUrl)})` : undefined,
    backgroundSize: 'cover',
    backgroundPosition: focal,
    backgroundRepeat: 'no-repeat',
    transform: framing.zoom !== 1 ? `scale(${framing.zoom})` : undefined,
    transformOrigin: focal,
  };

  return (
    <div
      className={cn('overflow-hidden', className)}
      style={{ backgroundColor: deskFallbackColor(fallbackColor) }}
      aria-hidden
    >
      {imageUrl && (
        <>
          <div className="absolute inset-0" style={imageStyle} />
          <div className="absolute inset-0" style={{ backgroundImage: HERO_OVERLAY }} />
        </>
      )}
    </div>
  );
}
