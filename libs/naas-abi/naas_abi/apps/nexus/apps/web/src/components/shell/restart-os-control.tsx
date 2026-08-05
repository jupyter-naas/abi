'use client';

import { useCallback, useEffect, useState } from 'react';
import { Loader2, Power } from 'lucide-react';

import {
  fetchOsStatus,
  requestRestartOs,
  waitForOsOnline,
  type OsStatus,
} from '@/lib/runtime';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';

type RestartPhase = 'idle' | 'restarting' | 'online' | 'error';

export function useRestartOs() {
  const [phase, setPhase] = useState<RestartPhase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<OsStatus | null>(null);

  const refreshStatus = useCallback(async () => {
    try {
      const next = await fetchOsStatus();
      setStatus(next);
      if (next.restarting) {
        setPhase('restarting');
      }
    } catch {
      /* status optional until user interacts */
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const restartOs = useCallback(async () => {
    setError(null);
    setPhase('restarting');
    try {
      const result = await requestRestartOs();
      if (!result.scheduled) {
        throw new Error(result.message || 'Restart was not scheduled');
      }
      const online = await waitForOsOnline();
      if (!online) {
        throw new Error('Restart timed out — check the server logs and try again.');
      }
      await refreshStatus();
      setPhase('online');
      window.setTimeout(() => setPhase('idle'), 4000);
    } catch (err) {
      setPhase('error');
      setError(err instanceof Error ? err.message : 'Failed to restart OS');
    }
  }, [refreshStatus]);

  return {
    phase,
    error,
    status,
    restartOs,
    refreshStatus,
    isRestarting: phase === 'restarting',
  };
}

interface RestartOsMenuItemProps {
  onClose?: () => void;
  className?: string;
}

export function RestartOsMenuItem({ onClose, className }: RestartOsMenuItemProps) {
  const isSuperadmin = useAuthStore((s) => !!s.user?.is_superadmin);
  const { phase, error, status, restartOs, isRestarting } = useRestartOs();

  if (!isSuperadmin) {
    return null;
  }

  const disabled = isRestarting || status?.dev_runtime_available === false;

  const label =
    phase === 'restarting'
      ? 'Restarting OS…'
      : phase === 'online'
        ? 'OS restarted'
        : 'Restart OS';

  return (
    <div className={cn('border-t border-border/60', className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          const confirmed = window.confirm(
            'Restart OS?\n\nThe platform will reload to apply module and configuration changes. Chat will reconnect automatically.',
          );
          if (!confirmed) return;
          onClose?.();
          void restartOs();
        }}
        className={cn(
          'flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors',
          disabled
            ? 'cursor-not-allowed text-muted-foreground/60'
            : 'text-foreground hover:bg-workspace-accent-10',
        )}
        title={
          status?.dev_runtime_available === false
            ? 'Restart OS is available in the local abi dev runtime'
            : 'Reload the ABI platform to apply config changes'
        }
      >
        {isRestarting ? (
          <Loader2 size={14} className="shrink-0 animate-spin" />
        ) : (
          <Power size={14} className="shrink-0" />
        )}
        <span className="flex-1 text-left">{label}</span>
      </button>
      {error ? (
        <p className="px-3 pb-2 text-[11px] text-destructive">{error}</p>
      ) : null}
      {status?.dev_runtime_available === false ? (
        <p className="px-3 pb-2 text-[10px] text-muted-foreground">
          Local dev runtime only — use your deployment supervisor in production.
        </p>
      ) : null}
    </div>
  );
}

interface RestartOsButtonProps {
  className?: string;
  variant?: 'primary' | 'ghost';
}

export function RestartOsButton({ className, variant = 'primary' }: RestartOsButtonProps) {
  const isSuperadmin = useAuthStore((s) => !!s.user?.is_superadmin);
  const { phase, error, status, restartOs, isRestarting } = useRestartOs();

  if (!isSuperadmin) {
    return null;
  }

  const disabled = isRestarting || status?.dev_runtime_available === false;

  return (
    <div className={className}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          void restartOs();
        }}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-60',
          variant === 'primary'
            ? 'bg-workspace-accent text-white hover:opacity-90'
            : 'border border-border text-foreground hover:bg-muted/50',
        )}
      >
        {isRestarting ? <Loader2 size={12} className="animate-spin" /> : <Power size={12} />}
        {phase === 'restarting' ? 'Restarting OS…' : 'Restart OS'}
      </button>
      {error ? <p className="mt-1 text-[11px] text-destructive">{error}</p> : null}
    </div>
  );
}
