import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

/** The one busy indicator. Inside a button, put it before the label ("Saving…"). */
export function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} aria-hidden="true" className={cn('shrink-0 animate-spin', className)} />;
}

/** A pane or a page that is loading: spinner and label, centred. */
export function Loading({ label = 'Loading…', className }: { label?: string; className?: string }) {
  return (
    <div
      role="status"
      aria-busy="true"
      className={cn('flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground', className)}
    >
      <Spinner />
      {label}
    </div>
  );
}
