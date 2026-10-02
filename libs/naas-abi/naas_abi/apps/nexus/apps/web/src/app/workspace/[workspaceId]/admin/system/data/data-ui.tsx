'use client';

/** Small building blocks shared by every service view of the data explorer. */
import { useEffect, useState, type ReactNode } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import { Check, Copy, type LucideIcon } from 'lucide-react';
import { absoluteTime, initials, relativeTime } from './data-model';

export type Tone = 'neutral' | 'accent' | 'success' | 'warn' | 'danger' | 'info';

export function Badge({
  children,
  tone = 'neutral',
  mono = false,
  title,
}: {
  children: ReactNode;
  tone?: Tone;
  mono?: boolean;
  title?: string;
}) {
  return (
    <span className={`data-badge data-badge-${tone}${mono ? ' data-badge-mono' : ''}`} title={title}>
      {children}
    </span>
  );
}

export function StatusPill({ tone, label, pulse = false }: { tone: Tone; label: string; pulse?: boolean }) {
  return (
    <span className={`data-pill data-pill-${tone}`}>
      <span className={pulse ? 'data-pill-dot data-pill-dot-pulse' : 'data-pill-dot'} aria-hidden="true" />
      {label}
    </span>
  );
}

export function IconTile({ icon: Icon, size = 'md' }: { icon: LucideIcon; size?: 'sm' | 'md' | 'lg' }) {
  const px = size === 'lg' ? 20 : size === 'sm' ? 14 : 16;
  return (
    <span className={`data-icon-tile data-icon-tile-${size}`} aria-hidden="true">
      <Icon size={px} strokeWidth={1.75} />
    </span>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="data-kbd">{children}</kbd>;
}

export function Hint({
  label,
  shortcut,
  children,
  side = 'top',
}: {
  label: string;
  shortcut?: string;
  children: ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
}) {
  return (
    <Tooltip.Root delayDuration={350}>
      <Tooltip.Trigger asChild>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="data-tooltip" side={side} sideOffset={6}>
          {label}
          {shortcut && <Kbd>{shortcut}</Kbd>}
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const timer = window.setTimeout(() => setDone(false), 1400);
    return () => window.clearTimeout(timer);
  }, [done]);
  return (
    <button
      type="button"
      className="data-icon-button"
      aria-label={done ? 'Copied' : label}
      title={done ? 'Copied' : label}
      onClick={(event) => {
        event.stopPropagation();
        void navigator.clipboard?.writeText(value).then(() => setDone(true));
      }}
    >
      {done ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
    </button>
  );
}

/** Re-renders every ``ms`` so relative times stay true while the page is open. */
export function useNow(ms = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(timer);
  }, [ms]);
  return now;
}

export function RelativeTime({ iso }: { iso: string | null | undefined }) {
  const now = useNow();
  if (!iso) return null;
  return (
    <time className="data-time" dateTime={iso} title={absoluteTime(iso)}>
      {relativeTime(iso, now)}
    </time>
  );
}

export function Avatar({ name }: { name: string }) {
  return (
    <span className="data-avatar" aria-hidden="true" title={name}>
      {initials(name)}
    </span>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="data-empty" role="status">
      <span className="data-empty-icon" aria-hidden="true">
        <Icon size={22} strokeWidth={1.5} />
      </span>
      <p className="data-empty-title">{title}</p>
      {children && <p className="data-empty-text">{children}</p>}
      {action && <div className="data-empty-action">{action}</div>}
    </div>
  );
}

export function SkeletonRows({ rows = 6 }: { rows?: number }) {
  return (
    <div className="data-skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="data-skeleton-row">
          <span className="data-skeleton-block data-skeleton-icon" />
          <span className="data-skeleton-block" style={{ width: `${40 + ((i * 17) % 35)}%` }} />
          <span className="data-skeleton-block data-skeleton-meta" />
        </div>
      ))}
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="data-field">
      <dt className="data-field-label">{label}</dt>
      <dd className="data-field-value">{children}</dd>
    </div>
  );
}

export function Notice({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <div className={`data-notice data-notice-${tone}`} role="status">
      {children}
    </div>
  );
}
