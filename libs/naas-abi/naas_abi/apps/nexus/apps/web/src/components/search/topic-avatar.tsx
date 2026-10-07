'use client';

import { useState } from 'react';
import { getApiUrl } from '@/lib/config';
import { cn } from '@/lib/utils';
import { initials, safeImage } from '@/lib/search-topics';

/** Image when the graph gives a loadable one, initials underneath otherwise. */
export function TopicAvatar({ label, image, size = 40, className, contain = false }: {
  label: string;
  image?: string | null;
  size?: number;
  className?: string;
  /** Draw the whole image (a logo) rather than cropping it to the square (a portrait). */
  contain?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const src = failed ? null : safeImage(image, getApiUrl());
  return (
    <div
      className={cn('relative flex flex-shrink-0 items-center justify-center overflow-hidden rounded-lg bg-workspace-accent-10 font-semibold text-workspace-accent', className)}
      style={{ width: size, height: size, fontSize: Math.max(11, size / 2.8) }}
      aria-hidden
    >
      {initials(label)}
      {src && (
        // eslint-disable-next-line @next/next/no-img-element -- arbitrary graph-provided hosts
        <img src={src} alt="" className={cn('absolute inset-0 h-full w-full', contain ? 'bg-white object-contain' : 'object-cover')} onError={() => setFailed(true)} />
      )}
    </div>
  );
}
