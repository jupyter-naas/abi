'use client';

import { cn } from '@/lib/utils';

/** A user's initial on the scope's primary tint: identity is the email beside it, not a colour. */
export function Avatar({ email, size = 22, className }: { email: string; size?: number; className?: string }) {
  const initial = (email[0] ?? '?').toUpperCase();
  return (
    <span
      aria-hidden
      className={cn(
        'flex flex-shrink-0 items-center justify-center rounded-full bg-primary/15 text-[10px] font-semibold text-primary',
        className
      )}
      style={{ width: size, height: size }}
    >
      {initial}
    </span>
  );
}
