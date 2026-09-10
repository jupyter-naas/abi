'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import {
  formatCompactTokens,
  type ContextUsageSnapshot,
  type ContextUsageTone,
} from '@/lib/chat-context-usage';

/** Same optical size as HardDrive (16). Plus is 20; a 20px ring reads heavier. */
const RING = 16;
const STROKE = 1.5;
const RADIUS = (RING - STROKE) / 2;
const CIRC = 2 * Math.PI * RADIUS;

const TONE_COLOR: Record<ContextUsageTone, string> = {
  calm: 'currentColor',
  warning: '#d97706',
  danger: '#dc2626',
};

const BUCKET_COLOR: Record<string, string> = {
  last_request: '#6366f1',
  conversation: '#6366f1',
  system: '#8b5cf6',
  draft: '#22c55e',
  attachments: '#0ea5e9',
};

export function ContextUsageMeter({ snapshot }: { snapshot: ContextUsageSnapshot }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const fill = Math.max(0, Math.min(1, snapshot.percent / 100));
  const dashOffset = CIRC * (1 - fill);
  const toneColor = TONE_COLOR[snapshot.tone];
  const usedLabel = `${snapshot.hasMeasuredUsage ? '' : '~'}${formatCompactTokens(snapshot.usedTokens)}`;
  const windowLabel = formatCompactTokens(snapshot.windowTokens);
  const percentLabel = `${Math.round(snapshot.percent)}%`;

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointer);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onPointer);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="relative shrink-0" ref={rootRef}>
      <button
        type="button"
        className={cn('chat-composer-action', open && 'is-active')}
        aria-label={`Context usage ${percentLabel}, ${usedLabel} of ${windowLabel} tokens`}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={snapshot.tooltip}
        onClick={() => setOpen((value) => !value)}
      >
        <svg
          width={RING}
          height={RING}
          viewBox={`0 0 ${RING} ${RING}`}
          aria-hidden
          className="chat-context-usage-ring"
        >
          <circle
            cx={RING / 2}
            cy={RING / 2}
            r={RADIUS}
            fill="none"
            stroke="currentColor"
            strokeOpacity={0.28}
            strokeWidth={STROKE}
          />
          <circle
            cx={RING / 2}
            cy={RING / 2}
            r={RADIUS}
            fill="none"
            stroke={toneColor}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={dashOffset}
            transform={`rotate(-90 ${RING / 2} ${RING / 2})`}
          />
        </svg>
      </button>

      {open && (
        <div
          className="chat-context-usage-popover"
          role="dialog"
          aria-label="Context Usage"
        >
          <div className="chat-context-usage-popover-head">
            <span className="chat-context-usage-popover-title">Context Usage</span>
            <span className={cn('chat-context-usage-percent', `is-${snapshot.tone}`)}>
              {percentLabel}
            </span>
          </div>
          <p className="chat-context-usage-total">
            {usedLabel} / {windowLabel} tokens
          </p>
          <div className="chat-context-usage-bar" aria-hidden>
            {snapshot.buckets
              .filter((bucket) => bucket.tokens > 0)
              .map((bucket) => (
                <span
                  key={bucket.id}
                  className="chat-context-usage-bar-seg"
                  style={{
                    width: `${Math.max(1.5, (bucket.tokens / Math.max(snapshot.usedTokens, 1)) * 100)}%`,
                    background: BUCKET_COLOR[bucket.id] ?? '#94a3b8',
                  }}
                />
              ))}
          </div>
          <ul className="chat-context-usage-list">
            {snapshot.buckets.map((bucket) => (
              <li key={bucket.id}>
                <span className="chat-context-usage-swatch-wrap">
                  <span
                    className="chat-context-usage-swatch"
                    style={{ background: BUCKET_COLOR[bucket.id] ?? '#94a3b8' }}
                  />
                  {bucket.label}
                </span>
                <span className="chat-context-usage-count">
                  {bucket.estimated ? '~' : ''}
                  {formatCompactTokens(bucket.tokens)}
                </span>
              </li>
            ))}
          </ul>
          {snapshot.reserveFootnote && (
            <p className="chat-context-usage-footnote">{snapshot.reserveFootnote}</p>
          )}
        </div>
      )}
    </div>
  );
}
