'use client';

import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  officeCreateStatus,
  type OfficeCreateKind,
  type OfficeCreatePhase,
} from './office-create';

export function OfficeCreateLoader({
  kind,
  phase,
  error,
}: {
  kind: OfficeCreateKind;
  phase: OfficeCreatePhase;
  error?: string | null;
}) {
  const status = officeCreateStatus(kind, phase);
  const pulse = error ? '' : 'animate-pulse';

  return (
    <div
      className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-auto bg-muted px-6 py-10"
      data-testid="office-create-loader"
      data-kind={kind}
      data-phase={error ? 'error' : phase}
      role="status"
      aria-live="polite"
      aria-busy={!error}
    >
      <div
        className={cn(
          'relative w-full overflow-hidden border border-border bg-background shadow-sm',
          kind === 'document'
            ? 'aspect-[8.5/11] max-h-[min(72vh,36rem)] max-w-[min(100%,22rem)]'
            : 'aspect-video max-w-xl',
        )}
        aria-hidden="true"
      >
        <div className="absolute inset-0 flex flex-col gap-3 p-8">
          <div className={cn('h-3 w-24 rounded-sm bg-muted-foreground/15', pulse)} />
          <div className={cn('mt-4 h-2 w-4/5 rounded-sm bg-muted-foreground/10', pulse)} />
          <div className={cn('h-2 w-3/5 rounded-sm bg-muted-foreground/10', pulse)} />
          <div className={cn('h-2 w-2/3 rounded-sm bg-muted-foreground/10', pulse)} />
        </div>
      </div>
      <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
        {!error && <Loader2 size={16} className="animate-spin" />}
        <span>{error || status}</span>
      </div>
    </div>
  );
}
