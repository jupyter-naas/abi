'use client';

import type { ReactNode } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';

export function LoadingBlock({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-20 text-sm text-muted-foreground">
      <Loader2 size={16} className="animate-spin" />
      {label}…
    </div>
  );
}

export function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center gap-2 border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
      <AlertTriangle size={16} />
      {message}
    </div>
  );
}

export function EmptyBlock({ children }: { children: ReactNode }) {
  return (
    <div className="py-16 text-center">
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  );
}
