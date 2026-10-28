'use client';

import type { CSSProperties } from 'react';
import { cn } from '@/lib/utils';
import { DEFAULT_FRAMING, type BackgroundFraming } from '@/lib/home-background';

/**
 * The Home desk wallpaper, drawn the same way on the desk and in the Edit
 * background image preview so what is framed there is what the desk shows:
 * the image covers the frame, its focal point (x%, y%) is kept in view, and
 * it is scaled by `zoom` around that point. A light workspace-accent tint keeps
 * desk icons legible.
 */
export function DeskWallpaper({
  imageUrl,
  framing = DEFAULT_FRAMING,
  className,
}: {
  imageUrl?: string;
  framing?: BackgroundFraming;
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
    <div className={cn('overflow-hidden bg-workspace-accent-30', className)} aria-hidden>
      {imageUrl && (
        <>
          <div className="absolute inset-0" style={imageStyle} />
          <div className="absolute inset-0 bg-workspace-accent-30" />
        </>
      )}
    </div>
  );
}
