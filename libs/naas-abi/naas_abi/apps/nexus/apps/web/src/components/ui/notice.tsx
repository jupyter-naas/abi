import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const tones = {
  info: 'border-border bg-muted/50 text-muted-foreground',
  success: 'border-primary/30 bg-primary/10 text-primary',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  error: 'border-destructive/30 bg-destructive/10 text-destructive',
} as const;

export type NoticeTone = keyof typeof tones;

/** An inline status line: a save confirmation, a load error, a warning. Errors are announced. */
export function Notice({
  tone = 'info',
  icon,
  children,
  className,
}: {
  tone?: NoticeTone;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2 border px-3 py-2 text-sm', tones[tone], className)}
    >
      {icon ? <span className="mt-0.5 shrink-0">{icon}</span> : null}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
