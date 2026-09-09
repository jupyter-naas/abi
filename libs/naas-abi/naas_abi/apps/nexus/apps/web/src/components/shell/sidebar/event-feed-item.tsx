'use client';

import React, { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { BFO_BUCKET_BY_TYPE } from '@/lib/bfo-buckets';
import {
  UNKNOWN,
  buildEventGraphPayload,
  eventSentence,
  eventTimestamp,
  formatEventClock,
  formatEventDate,
  summarizeBucket,
  type BfoBucketType,
} from '@/app/workspace/[workspaceId]/admin/events/bfo-event-projection';
import type { EventRow } from '@/stores/events';

/** Buckets carried under the title, in BFO book order after Who/What/When. */
const META_BUCKETS: BfoBucketType[] = ['Site', 'Quality', 'Realizable', 'GDC'];

function initialsOf(label: string): string {
  const cleaned = label.replace(/[^A-Za-z0-9]+/g, ' ').trim();
  if (!cleaned) return '?';
  const words = cleaned.split(' ');
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

export const EventFeedItem = React.memo(function EventFeedItem({
  row,
  active,
  onSelect,
}: {
  row: EventRow;
  active: boolean;
  onSelect: () => void;
}) {
  const payload = useMemo(() => buildEventGraphPayload(row.event), [row.event]);
  const who = summarizeBucket(payload, 'Material Entity').split(' · ')[0];
  const at = eventTimestamp(row.event) ?? row.receivedAt;
  const materialDef = BFO_BUCKET_BY_TYPE['Material Entity'];
  const unknownDef = BFO_BUCKET_BY_TYPE.Unknown;
  const knownWho = who !== UNKNOWN;

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'flex w-full gap-2 rounded-md px-2 py-2 text-left transition-colors',
        active ? 'bg-muted text-foreground' : 'hover:bg-muted/60',
      )}
    >
      <span
        className="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-[9px] font-semibold text-white"
        style={{
          backgroundColor: knownWho ? materialDef.color : unknownDef.color,
          border: `1px solid ${knownWho ? materialDef.border : unknownDef.border}`,
          borderStyle: knownWho ? 'solid' : 'dashed',
        }}
        title={`Material entity · ${who}`}
      >
        {knownWho ? initialsOf(who) : '?'}
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate text-xs font-semibold">
            {payload.naming.verb}
            {payload.naming.object !== UNKNOWN && (
              <span className="font-normal text-muted-foreground"> · {payload.naming.object}</span>
            )}
          </span>
          <span className="flex-shrink-0 text-right font-mono text-[9px] leading-tight text-muted-foreground">
            <span className="block">{formatEventClock(at)}</span>
            <span className="block opacity-70">{formatEventDate(at)}</span>
          </span>
        </span>

        <span className="mt-0.5 block truncate text-[10px] text-muted-foreground">
          {eventSentence(payload)}
        </span>

        <span className="mt-1 flex flex-wrap gap-1">
          {META_BUCKETS.map((bucket) => {
            const value = summarizeBucket(payload, bucket);
            const known = value !== UNKNOWN;
            const def = BFO_BUCKET_BY_TYPE[bucket];
            return (
              <span
                key={bucket}
                title={`${bucket}: ${value}`}
                className={cn(
                  'flex max-w-full items-center gap-1 rounded border px-1 py-px font-mono text-[9px]',
                  known ? 'border-border text-muted-foreground' : 'border-dashed border-border/60 text-muted-foreground/60',
                )}
              >
                <span
                  className="inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full"
                  style={{ backgroundColor: known ? def.color : 'transparent', border: `1px solid ${def.border}` }}
                />
                <span className="truncate">{value}</span>
              </span>
            );
          })}
        </span>
      </span>
    </button>
  );
});
