'use client';

import {
  AlertCircle,
  Bot,
  Box,
  Database,
  KeyRound,
  Layers,
  Mail,
  Radio,
  Shield,
  Waypoints,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { useAdminEventsLog } from '@/app/workspace/[workspaceId]/admin/events/admin-events-log';
import {
  projectEventToFeedItem,
  type EventKind,
} from '@/app/workspace/[workspaceId]/admin/events/event-feed';
import { cn } from '@/lib/utils';

const KIND_ICON: Record<EventKind, { icon: LucideIcon; color: string; bg: string }> = {
  object: { icon: Box, color: 'text-sky-700', bg: 'bg-sky-500/10' },
  agent: { icon: Bot, color: 'text-violet-700', bg: 'bg-violet-500/10' },
  cache: { icon: Zap, color: 'text-amber-700', bg: 'bg-amber-500/10' },
  keyvalue: { icon: KeyRound, color: 'text-teal-700', bg: 'bg-teal-500/10' },
  email: { icon: Mail, color: 'text-pink-700', bg: 'bg-pink-500/10' },
  graph: { icon: Waypoints, color: 'text-indigo-700', bg: 'bg-indigo-500/10' },
  secret: { icon: Shield, color: 'text-slate-700', bg: 'bg-slate-500/10' },
  bus: { icon: Radio, color: 'text-orange-700', bg: 'bg-orange-500/10' },
  vector: { icon: Layers, color: 'text-emerald-700', bg: 'bg-emerald-500/10' },
  error: { icon: AlertCircle, color: 'text-rose-700', bg: 'bg-rose-500/10' },
  default: { icon: Database, color: 'text-muted-foreground', bg: 'bg-muted' },
};

export function EventsFeedSection() {
  const events = useAdminEventsLog((s) => s.events);
  const selectedUri = useAdminEventsLog((s) => s.selectedUri);
  const toggleUri = useAdminEventsLog((s) => s.toggleUri);
  const classFilter = useAdminEventsLog((s) => s.classFilter);
  const setClassFilter = useAdminEventsLog((s) => s.setClassFilter);
  const searchInput = useAdminEventsLog((s) => s.searchInput);
  const setSearchInput = useAdminEventsLog((s) => s.setSearchInput);
  const search = useAdminEventsLog((s) => s.search);
  const availableTypes = useAdminEventsLog((s) => s.availableTypes);
  const lastPollAt = useAdminEventsLog((s) => s.lastPollAt);
  const secondsToNextPoll = useAdminEventsLog((s) => s.secondsToNextPoll);
  const filtering = Boolean(classFilter || search);

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex shrink-0 flex-col gap-2">
        <div className="flex items-center gap-2 px-0.5 text-xs" aria-live="polite">
          <span
            className={`inline-block h-2 w-2 shrink-0 rounded-full ${
              lastPollAt ? 'bg-green-500' : 'bg-zinc-400'
            }`}
          />
          <span className="min-w-0 text-muted-foreground">
            {lastPollAt
              ? `last ${lastPollAt.toLocaleTimeString()} · next in ${secondsToNextPoll}s`
              : 'polling…'}
          </span>
        </div>
        <select
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          className="w-full rounded border bg-background px-2 py-1 text-xs"
          title="Filter by event type (server-side: returns the last N of this type)"
          aria-label="Event type"
        >
          <option value="">All event types ({availableTypes.length})</option>
          {availableTypes.map((t) => (
            <option key={t.uri} value={t.uri}>
              {t.label}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search payload…"
          aria-label="Search payload"
          className="w-full rounded border bg-background px-2 py-1 text-xs"
        />
      </div>
      {events.length === 0 ? (
        <p className="px-1 py-3 text-xs text-muted-foreground">
          {filtering ? 'No events match the current filters.' : 'Waiting for events…'}
        </p>
      ) : (
        <ul
          data-testid="admin-events-feed"
          aria-label="Events"
          className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto"
        >
          {events.map((event) => {
            const item = projectEventToFeedItem(event);
            const meta = KIND_ICON[item.kind];
            const Icon = meta.icon;
            const selected = event._uri === selectedUri;
            return (
              <li key={event._uri}>
                <button
                  type="button"
                  onClick={() => toggleUri(event._uri)}
                  aria-pressed={selected}
                  className={cn(
                    'flex w-full gap-2.5 rounded-lg border px-2.5 py-2 text-left text-foreground transition-colors',
                    selected
                      ? 'border-border bg-muted'
                      : 'border-border bg-background hover:bg-muted/40',
                  )}
                >
                  <span
                    className={cn(
                      'mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md',
                      meta.bg,
                      meta.color,
                    )}
                  >
                    <Icon size={14} aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-start justify-between gap-2">
                      <span className="truncate text-[13px] font-medium leading-5">
                        {item.line1}
                      </span>
                      {item.timeLabel ? (
                        <span className="shrink-0 pt-0.5 text-[11px] text-muted-foreground">
                          {item.timeLabel}
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-0.5 block truncate text-[12px] leading-4 text-muted-foreground">
                      {item.line2}
                    </span>
                    {item.line3 ? (
                      <span className="mt-0.5 block truncate text-[12px] leading-4 text-muted-foreground">
                        {item.line3}
                      </span>
                    ) : null}
                    {item.line4 ? (
                      <span className="mt-0.5 block truncate text-[12px] leading-4 text-muted-foreground">
                        {item.line4}
                      </span>
                    ) : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
