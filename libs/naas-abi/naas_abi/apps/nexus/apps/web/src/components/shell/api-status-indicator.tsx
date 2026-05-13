'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
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
  const radiusPx = 6 + Math.random() * 8; // 6–14
  const durationS = 1.6 + Math.random() * 3; // 1.6–4.6
  const lightness = 35 + Math.random() * 50; // 35%–85% — full range of greys
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

export function ApiStatusIndicator() {
  const apiUrl = getApiUrl();
  const [status, setStatus] = useState<Status>('checking');
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);
  const [hovered, setHovered] = useState(false);
  const [popoverPos, setPopoverPos] = useState<{ top: number; right: number } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const inflight = useNetworkActivityStore((state) => state.inflight);
  const totalStarted = useNetworkActivityStore((state) => state.totalStarted);
  const totalCompleted = useNetworkActivityStore((state) => state.totalCompleted);
  const sessionStartedAt = useNetworkActivityStore((state) => state.sessionStartedAt);
  const mountedRef = useRef(true);

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

  // Tick a 1s timer so the hover popover's "uptime" / "last checked" stays fresh.
  useEffect(() => {
    if (!hovered) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [hovered]);

  // Anchor the portal popover to the trigger button. Recompute on hover and on
  // window resize/scroll so it stays attached.
  useLayoutEffect(() => {
    if (!hovered) {
      setPopoverPos(null);
      return;
    }
    const updatePos = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setPopoverPos({
        top: rect.bottom + 8,
        right: Math.max(0, window.innerWidth - rect.right),
      });
    };
    updatePos();
    window.addEventListener('resize', updatePos);
    window.addEventListener('scroll', updatePos, true);
    return () => {
      window.removeEventListener('resize', updatePos);
      window.removeEventListener('scroll', updatePos, true);
    };
  }, [hovered]);

  const label =
    status === 'online'
      ? 'API: connected'
      : status === 'offline'
        ? 'API: unreachable — click to open it in a new tab'
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

  return (
    <div
      className="relative"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        ref={triggerRef}
        type="button"
        onClick={handleClick}
        aria-label={label}
        className={cn(
          'flex h-8 items-center gap-4 rounded-md px-2 text-xs transition-colors',
          'hover:bg-muted',
          status === 'offline' ? 'text-destructive' : 'text-muted-foreground'
        )}
      >
        <span className="relative inline-flex h-2 w-2 items-center justify-center">
          {/* Orbiting satellites — one per in-flight request, each with a random orbit */}
          {satellites.map((profile, i) => (
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
          <span className={cn('relative inline-block h-2 w-2 rounded-full', dotClass)} />
        </span>
        <span className="hidden sm:inline">
          {status === 'online' ? 'API' : status === 'offline' ? 'API offline' : 'API…'}
        </span>
      </button>

      {hovered && popoverPos && typeof document !== 'undefined' && createPortal(
        <div
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          style={{ position: 'fixed', top: popoverPos.top, right: popoverPos.right, zIndex: 2147483647 }}
          className="glass-card w-72 rounded-lg border bg-card p-3 text-xs shadow-lg"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="font-medium text-foreground">API status</span>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-[10px] font-medium',
                status === 'online' && 'bg-green-500/15 text-green-500',
                status === 'offline' && 'bg-red-500/15 text-red-500',
                status === 'checking' && 'bg-amber-500/15 text-amber-500',
              )}
            >
              {status === 'online' ? 'connected' : status === 'offline' ? 'unreachable' : 'checking'}
            </span>
          </div>

          <dl className="space-y-1.5 text-muted-foreground">
            <div className="flex items-baseline justify-between gap-2">
              <dt>URL</dt>
              <dd className="min-w-0 truncate font-mono text-[11px] text-foreground" title={apiUrl}>
                {apiUrl}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt>In flight</dt>
              <dd className="text-foreground">
                {inflight}
                {inflight > MAX_VISIBLE_SATELLITES && (
                  <span className="ml-1 text-muted-foreground">
                    ({MAX_VISIBLE_SATELLITES} shown)
                  </span>
                )}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt>Requests this session</dt>
              <dd className="text-foreground">
                {totalStarted}
                <span className="ml-1 text-muted-foreground">
                  ({totalCompleted} done)
                </span>
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt>Session uptime</dt>
              <dd className="text-foreground">{formatDuration(sessionMs)}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <dt>Last health check</dt>
              <dd className="text-foreground">
                {lastCheckedMs === null
                  ? 'never'
                  : lastCheckedMs < 1000
                    ? 'just now'
                    : `${formatDuration(lastCheckedMs)} ago`}
              </dd>
            </div>
          </dl>

          {status === 'offline' && (
            <p className="mt-2 border-t border-border/50 pt-2 text-[11px] text-destructive">
              Click the indicator to open the API URL in a new tab.
            </p>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
}
