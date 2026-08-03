'use client';

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
} from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/config';
import { useNetworkActivityStore } from '@/stores/network-activity';

type Status = 'checking' | 'online' | 'offline';

const POLL_INTERVAL_MS = 15_000;
const REQUEST_TIMEOUT_MS = 5_000;
const MAX_VISIBLE_SATELLITES = 12;

type OrbitProfile = {
  radiusPx: number;
  durationS: number;
  reverse: boolean;
  delayS: number;
  color: string;
  opacity: number;
};

function makeOrbitProfile(): OrbitProfile {
  const radiusPx = 6 + Math.random() * 8; // 6-14
  const durationS = 1.6 + Math.random() * 3; // 1.6-4.6
  const lightness = 35 + Math.random() * 50; // 35%-85% grey range
  return {
    radiusPx,
    durationS,
    reverse: Math.random() < 0.5,
    delayS: -Math.random() * durationS,
    color: `hsl(0, 0%, ${lightness}%)`,
    opacity: 0.45 + Math.random() * 0.4,
  };
}

function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

type PopoverPos = {
  /** Footer (compact) opens above; navbar opens below. */
  placement: 'above' | 'below';
  top?: number;
  bottom?: number;
  right: number;
};

export function ApiStatusIndicator({ compact = false }: { compact?: boolean } = {}) {
  const apiUrl = getApiUrl();
  const [status, setStatus] = useState<Status>('checking');
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);
  const [open, setOpen] = useState(false);
  const [popoverPos, setPopoverPos] = useState<PopoverPos | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflight = useNetworkActivityStore((state) => state.inflight);
  const totalStarted = useNetworkActivityStore((state) => state.totalStarted);
  const totalCompleted = useNetworkActivityStore((state) => state.totalCompleted);
  const sessionStartedAt = useNetworkActivityStore((state) => state.sessionStartedAt);
  const mountedRef = useRef(true);

  const keepOpen = useCallback(() => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setOpen(true);
  }, []);

  const scheduleClose = useCallback(() => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    // Small delay so pointer/focus can move from trigger into the portal panel.
    closeTimerRef.current = setTimeout(() => setOpen(false), 120);
  }, []);

  const check = useCallback(async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(`${apiUrl}/health`, {
        method: 'GET',
        signal: controller.signal,
        cache: 'no-store',
      });
      if (!mountedRef.current) return;
      setStatus(response.ok ? 'online' : 'offline');
    } catch {
      if (!mountedRef.current) return;
      setStatus('offline');
    } finally {
      clearTimeout(timer);
      if (mountedRef.current) setLastCheckedAt(new Date());
    }
  }, [apiUrl]);

  useEffect(() => {
    mountedRef.current = true;
    check();
    const interval = setInterval(check, POLL_INTERVAL_MS);
    const onFocus = () => check();
    const onVisible = () => {
      if (document.visibilityState === 'visible') check();
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [check]);

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, []);

  // Tick a 1s timer so the open panel's "uptime" / "last checked" stays fresh.
  useEffect(() => {
    if (!open) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [open]);

  // Anchor the portal panel to the trigger. Compact (footer) opens upward so it
  // stays on-screen; non-compact (navbar) opens downward.
  useLayoutEffect(() => {
    if (!open) {
      setPopoverPos(null);
      return;
    }
    const updatePos = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const right = Math.max(8, window.innerWidth - rect.right);
      if (compact) {
        setPopoverPos({
          placement: 'above',
          bottom: Math.max(8, window.innerHeight - rect.top + 6),
          right,
        });
      } else {
        setPopoverPos({
          placement: 'below',
          top: rect.bottom + 8,
          right,
        });
      }
    };
    updatePos();
    window.addEventListener('resize', updatePos);
    window.addEventListener('scroll', updatePos, true);
    return () => {
      window.removeEventListener('resize', updatePos);
      window.removeEventListener('scroll', updatePos, true);
    };
  }, [open, compact]);

  const label =
    status === 'online'
      ? 'API: connected'
      : status === 'offline'
        ? 'API: unreachable; click to open it in a new tab'
        : 'API: checking…';

  const dotClass = cn(
    status === 'online' && 'bg-green-500',
    status === 'offline' && 'bg-red-500',
    status === 'checking' && 'bg-amber-500 animate-pulse',
  );

  const handleClick = () => {
    if (status === 'offline') {
      window.open(apiUrl, '_blank', 'noopener,noreferrer');
    } else {
      setStatus('checking');
      check();
    }
  };

  const satelliteCount = status === 'online' ? Math.min(inflight, MAX_VISIBLE_SATELLITES) : 0;
  // Stable per-slot random orbit profiles so satellites don't flicker with each render.
  const orbitProfilesRef = useRef<OrbitProfile[]>([]);
  while (orbitProfilesRef.current.length < satelliteCount) {
    orbitProfilesRef.current.push(makeOrbitProfile());
  }
  const satellites = orbitProfilesRef.current.slice(0, satelliteCount);

  const sessionMs = Math.max(0, now - sessionStartedAt);
  const lastCheckedMs = lastCheckedAt ? Math.max(0, now - lastCheckedAt.getTime()) : null;

  const panelStyle: CSSProperties = {
    position: 'fixed',
    right: popoverPos?.right,
    zIndex: 2147483647,
    ...(popoverPos?.placement === 'above'
      ? { bottom: popoverPos.bottom }
      : { top: popoverPos?.top }),
  };

  return (
    <div
      className="relative"
      onMouseEnter={keepOpen}
      onMouseLeave={scheduleClose}
    >
      <button
        ref={triggerRef}
        type="button"
        onClick={handleClick}
        onFocus={keepOpen}
        onBlur={scheduleClose}
        aria-label={label}
        aria-expanded={open}
        aria-haspopup="dialog"
        className={cn(
          'flex items-center transition-colors',
          'hover:bg-muted',
          status === 'offline' ? 'text-destructive' : 'text-muted-foreground',
          compact
            ? 'h-6 gap-1 rounded px-1.5 text-[11px]'
            : 'h-8 gap-4 rounded-md px-2 text-xs',
        )}
      >
        <span
          className={cn(
            'relative inline-flex items-center justify-center',
            compact ? 'h-1.5 w-1.5' : 'h-2 w-2',
          )}
        >
          {/* Orbiting satellites: one per in-flight request, each with a random orbit */}
          {!compact &&
            satellites.map((profile, i) => (
              <span
                key={i}
                aria-hidden
                className="pointer-events-none absolute inset-0"
                style={{
                  animation: `api-status-orbit ${profile.durationS}s linear infinite`,
                  animationDirection: profile.reverse ? 'reverse' : 'normal',
                  animationDelay: `${profile.delayS}s`,
                }}
              >
                <span
                  className="absolute left-1/2 top-1/2 block h-1 w-1 rounded-full"
                  style={{
                    backgroundColor: profile.color,
                    opacity: profile.opacity,
                    transform: `translate(-50%, -50%) translateY(-${profile.radiusPx}px)`,
                  }}
                />
              </span>
            ))}
          <span
            className={cn(
              'relative inline-block rounded-full',
              compact ? 'h-1.5 w-1.5' : 'h-2 w-2',
              dotClass,
            )}
          />
        </span>
        <span className="hidden sm:inline">
          {status === 'online' ? 'API' : status === 'offline' ? 'API offline' : 'API…'}
        </span>
        {compact && inflight > 0 && status === 'online' ? (
          <span
            className="tabular-nums text-foreground/80"
            title={`${inflight} in flight`}
          >
            {inflight}
          </span>
        ) : null}
      </button>

      {open && popoverPos && typeof document !== 'undefined' && createPortal(
        <div
          role="dialog"
          aria-label="API status details"
          onMouseEnter={keepOpen}
          onMouseLeave={scheduleClose}
          onFocusCapture={keepOpen}
          onBlurCapture={scheduleClose}
          style={panelStyle}
          className={cn(
            'border bg-card text-muted-foreground shadow-lg',
            compact
              ? 'w-64 rounded-md border-border/70 p-2.5 text-[11px]'
              : 'glass-card w-72 rounded-lg p-3 text-xs',
          )}
        >
          <div className={cn('flex items-center justify-between', compact ? 'mb-1.5' : 'mb-2')}>
            <span className="font-medium text-foreground">API status</span>
            <span
              className={cn(
                'font-medium',
                compact
                  ? 'text-[10px] uppercase tracking-wide'
                  : 'rounded-full px-2 py-0.5 text-[10px]',
                status === 'online' && (compact ? 'text-green-600' : 'bg-green-500/15 text-green-500'),
                status === 'offline' && (compact ? 'text-red-600' : 'bg-red-500/15 text-red-500'),
                status === 'checking' && (compact ? 'text-amber-600' : 'bg-amber-500/15 text-amber-500'),
              )}
            >
              {status === 'online' ? 'connected' : status === 'offline' ? 'unreachable' : 'checking'}
            </span>
          </div>

          <dl className={cn('text-muted-foreground', compact ? 'space-y-1' : 'space-y-1.5')}>
            <div className="flex items-baseline justify-between gap-2">
              <dt>URL</dt>
              <dd
                className={cn(
                  'min-w-0 truncate font-mono text-foreground',
                  compact ? 'text-[10px]' : 'text-[11px]',
                )}
                title={apiUrl}
              >
                {apiUrl}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt>In flight</dt>
              <dd className="tabular-nums text-foreground">
                {inflight}
                {!compact && inflight > MAX_VISIBLE_SATELLITES && (
                  <span className="ml-1 text-muted-foreground">
                    ({MAX_VISIBLE_SATELLITES} shown)
                  </span>
                )}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt>Requests this session</dt>
              <dd className="tabular-nums text-foreground">
                {totalStarted}
                <span className="ml-1 text-muted-foreground">
                  ({totalCompleted} done)
                </span>
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt>Session uptime</dt>
              <dd className="tabular-nums text-foreground">{formatDuration(sessionMs)}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt>Last health check</dt>
              <dd className="tabular-nums text-foreground">
                {lastCheckedMs === null
                  ? 'never'
                  : lastCheckedMs < 1000
                    ? 'just now'
                    : `${formatDuration(lastCheckedMs)} ago`}
              </dd>
            </div>
          </dl>

          {status === 'offline' && (
            <p
              className={cn(
                'border-t border-border/50 text-destructive',
                compact ? 'mt-1.5 pt-1.5 text-[10px]' : 'mt-2 pt-2 text-[11px]',
              )}
            >
              Click the indicator to open the API URL in a new tab.
            </p>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
}
