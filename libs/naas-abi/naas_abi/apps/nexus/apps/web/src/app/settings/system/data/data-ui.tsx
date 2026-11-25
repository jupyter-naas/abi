'use client';

/**
 * What the data explorer adds to the kit (`components/ui`): a status pill, a keyboard key,
 * a tooltip, a copy button, relative times, an avatar and a property row. Badges, notices,
 * empty states, dialogs and toasts come from the kit.
 */
import { useEffect, useState, type ReactNode } from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import { Check, Copy } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { absoluteTime, initials, relativeTime } from './data-model';

/** The kit's badge variants (``ui/badge``), used for every status tone of the explorer. */
export type Tone = 'neutral' | 'primary' | 'success' | 'warning' | 'destructive' | 'info';

/** A kit badge led by a status dot (pulsing while something runs). */
export function StatusPill({ tone, label, pulse = false }: { tone: Tone; label: string; pulse?: boolean }) {
  return (
    <Badge variant={tone} className="data-pill">
      <span className={`data-pill-dot${pulse ? ' data-pill-dot-pulse' : ''}`} aria-hidden="true" />
      {label}
    </Badge>
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
    <Button
      variant="ghost"
      size="icon"
      className="data-copy-button h-7 w-7"
      aria-label={done ? 'Copied' : label}
      title={done ? 'Copied' : label}
      onClick={(event) => {
        event.stopPropagation();
        void navigator.clipboard?.writeText(value).then(() => setDone(true));
      }}
    >
      {done ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
    </Button>
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

/** One label / value row of a property list (``<dl>``). Not a form field: see ``ui/field``. */
export function Property({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="data-field">
      <dt className="data-field-label">{label}</dt>
      <dd className="data-field-value">{children}</dd>
    </div>
  );
}
