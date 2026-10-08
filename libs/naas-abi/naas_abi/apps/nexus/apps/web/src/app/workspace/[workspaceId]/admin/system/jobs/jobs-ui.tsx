'use client';

/** Building blocks of the Jobs tab: status, recent-runs strip, triggers, countdowns. */
import { Clock, Hand, Radio, type LucideIcon } from 'lucide-react';
import { absoluteTime, formatDuration } from '../data/data-model';
import { Hint, StatusPill, useNow } from '../data/data-ui';
import { formatMs, isActive, runDuration, statusLabel, statusTone, triggerLabel } from './jobs-model';
import type { RunSummary } from './jobs-types';

export function RunStatus({ status }: { status: string }) {
  return <StatusPill tone={statusTone(status)} label={statusLabel(status)} pulse={isActive(status)} />;
}

const TRIGGER_ICONS: Record<string, LucideIcon> = { schedule: Clock, manual: Hand, event: Radio };

export function TriggerTag({ kind }: { kind: string }) {
  const Icon = TRIGGER_ICONS[kind] ?? Clock;
  return (
    <span className="jobs-trigger-tag">
      <Icon size={12} aria-hidden="true" />
      {triggerLabel(kind)}
    </span>
  );
}

/** "in 4 min 12 s", "due now", or a date for far ticks; re-renders every second. */
export function Countdown({ iso }: { iso: string | null }) {
  const now = useNow(1000);
  if (!iso) return <span className="data-muted">—</span>;
  const seconds = Math.round((Date.parse(iso) - now) / 1000);
  if (Number.isNaN(seconds)) return <span className="data-muted">—</span>;
  const text =
    seconds <= 0
      ? 'due now'
      : seconds < 3600
        ? `in ${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, '0')} s`
        : `in ${formatDuration(seconds)}`;
  return (
    <time className={seconds <= 60 ? 'jobs-countdown jobs-countdown-soon' : 'jobs-countdown'} dateTime={iso} title={absoluteTime(iso)}>
      {text}
    </time>
  );
}

export function RunDuration({ run }: { run: RunSummary }) {
  const now = useNow(isActive(run.status) ? 1000 : 60_000);
  const value = runDuration(run, now);
  return <span className="data-num">{formatMs(value)}</span>;
}

/** The last runs as squares, oldest left; each opens its run. */
export function RunStrip({
  runs,
  slots = 20,
  onOpen,
}: {
  runs: RunSummary[];
  slots?: number;
  onOpen?: (run: RunSummary) => void;
}) {
  const shown = runs.slice(0, slots).reverse();
  const empty = Math.max(0, slots - shown.length);
  return (
    <span className="jobs-strip" aria-label={`Last ${shown.length} runs`}>
      {Array.from({ length: empty }, (_, i) => (
        <span key={`empty-${i}`} className="jobs-strip-cell jobs-strip-empty" aria-hidden="true" />
      ))}
      {shown.map((run) => (
        <Hint
          key={run.key}
          label={`${statusLabel(run.status)} · ${absoluteTime(run.started_at ?? run.fired_at)} · ${formatMs(runDuration(run))}`}
        >
          <button
            type="button"
            className={`jobs-strip-cell jobs-strip-${run.status.toLowerCase()}`}
            aria-label={`${statusLabel(run.status)} run ${run.run_id}`}
            onClick={(event) => {
              event.stopPropagation();
              onOpen?.(run);
            }}
          />
        </Hint>
      ))}
    </span>
  );
}
