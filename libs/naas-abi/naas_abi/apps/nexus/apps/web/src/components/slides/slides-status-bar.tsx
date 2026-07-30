'use client';

import { GitBranch, RefreshCw } from 'lucide-react';
import { ApiStatusIndicator } from '@/components/shell/api-status-indicator';
import { useSlidesStore } from '@/stores/slides';
import { cn } from '@/lib/utils';

function statusLabel(status: string, phase: string | null): string {
  if (status === 'ready') return phase || 'ready';
  if (status === 'degraded') return phase || 'degraded';
  if (status === 'error') return phase || 'unavailable';
  if (status === 'ensuring') return 'starting';
  return 'idle';
}

function statusDotClass(status: string): string {
  if (status === 'ready') return 'bg-green-500';
  if (status === 'degraded') return 'bg-amber-500';
  if (status === 'error') return 'bg-red-500';
  if (status === 'ensuring') return 'bg-amber-500 animate-pulse';
  return 'bg-muted-foreground/40';
}

export interface SlidesStatusBarProps {
  onRefresh?: () => void;
  refreshing?: boolean;
}

/**
 * Thin opencode-style status bar for Slides: Forgejo branch, Coder workspace,
 * runtime status, and the API health indicator (moved out of the navbar).
 */
export function SlidesStatusBar({ onRefresh, refreshing }: SlidesStatusBarProps) {
  const runtimeStatus = useSlidesStore((s) => s.runtimeStatus);
  const forgejoBranch = useSlidesStore((s) => s.forgejoBranch);
  const coderWorkspace = useSlidesStore((s) => s.coderWorkspace);
  const coderPhase = useSlidesStore((s) => s.coderPhase);
  const selectedSlug = useSlidesStore((s) => s.selectedSlug);

  const branch = forgejoBranch || (selectedSlug ? `slides/${selectedSlug}` : null);
  const workspace = coderWorkspace || (selectedSlug ? `slides-${selectedSlug}` : null);

  return (
    <footer
      className={cn(
        'flex h-7 shrink-0 items-center justify-between gap-3 border-t border-border/60',
        'bg-muted/40 px-3 text-[11px] text-muted-foreground',
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        {branch ? (
          <span className="inline-flex min-w-0 items-center gap-1.5" title="Forgejo branch">
            <GitBranch size={11} className="shrink-0 opacity-70" />
            <span className="truncate font-medium text-foreground/90">{branch}</span>
          </span>
        ) : (
          <span className="text-muted-foreground/70">No deck open</span>
        )}
        {workspace ? (
          <span
            className="inline-flex min-w-0 items-center gap-1.5 border-l border-border/60 pl-3"
            title="Coder workspace"
          >
            <span
              className={cn('inline-block h-1.5 w-1.5 shrink-0 rounded-sm', statusDotClass(runtimeStatus))}
              aria-hidden
            />
            <span className="truncate font-mono text-[11px] text-foreground/90">{workspace}</span>
            <span className="shrink-0 text-muted-foreground/80">
              {statusLabel(runtimeStatus, coderPhase)}
            </span>
          </span>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className={cn(
              'inline-flex items-center gap-1 rounded px-1.5 py-0.5 transition-colors',
              'hover:bg-muted hover:text-foreground',
              refreshing && 'opacity-60',
            )}
            title="Refresh deck from Forgejo (⌘R)"
          >
            <RefreshCw size={11} className={cn(refreshing && 'animate-spin')} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        ) : null}
        <ApiStatusIndicator />
      </div>
    </footer>
  );
}
