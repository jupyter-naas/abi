'use client';

import { useState } from 'react';
import { Activity, Clock, Eye, FileText, Layers, Repeat } from 'lucide-react';
import { cn } from '@/lib/utils';
import { BarList } from '../bar-list';
import { Card } from '../card';
import { EventIcon, formatEventName } from '../event-icon';
import { formatDateTime, formatDuration, formatRelative, formatTime } from '../format';
import { KpiCard } from '../kpi-card';
import { scopeHasWorkspaces } from '../scope';
import { EmptyBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import type { AnalyticsTabProps } from '../tabs';
import type { AnalyticsEvent, UserDetail } from '../types';

const HISTORY_SHOWN = 100;

/** One member's activity in the period (`GET {base}/analytics/users/{user_id}`). */
export function UserDetailTab({
  scope,
  filters,
  timeZone,
  onClear,
}: AnalyticsTabProps & { onClear: () => void }) {
  const { data, loading, error, status } = useAnalytics<UserDetail>(
    scope,
    `/users/${encodeURIComponent(filters.userId)}`,
    filters
  );
  const [expandedSession, setExpandedSession] = useState<string | null>(null);

  if (loading && !data) return <LoadingBlock />;
  if (error)
    return (
      <Card
        title="Could not load this user"
        action={
          <button type="button" onClick={onClear} className="text-xs text-primary hover:underline">
            Clear the user filter
          </button>
        }
      >
        <EmptyBlock>{status === 404 ? 'This user is not a member of this scope.' : error}</EmptyBlock>
      </Card>
    );
  if (!data) return null;

  const eventsBySession = new Map<string, AnalyticsEvent[]>();
  for (const e of data.events) {
    const list = eventsBySession.get(e.session_id) ?? [];
    list.push(e);
    eventsBySession.set(e.session_id, list);
  }
  const workspaces = scopeHasWorkspaces(scope);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <KpiCard
          label="First seen"
          value={formatRelative(data.first_seen)}
          hint={formatDateTime(data.first_seen, timeZone)}
          icon={Clock}
        />
        <KpiCard
          label="Last seen"
          value={formatRelative(data.last_seen)}
          hint={formatDateTime(data.last_seen, timeZone)}
          icon={Activity}
        />
        <KpiCard label="Sessions" value={data.total_sessions} icon={Repeat} />
        <KpiCard label="Page views" value={data.total_page_views} icon={Eye} />
        <KpiCard
          label="Most visited page"
          value={data.most_visited_page?.title ?? '—'}
          hint={data.most_visited_page ? `${data.most_visited_page.views} views` : undefined}
          icon={FileText}
        />
        <KpiCard
          label="Workspaces used"
          value={data.workspaces_used.length}
          hint={data.workspaces_used.map((w) => w.name).join(', ') || undefined}
          icon={Layers}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Pages visited">
            <BarList
              items={data.pages.map((p) => ({
                key: p.page_path,
                label: p.page_title,
                sublabel: p.page_path,
                value: p.views,
              }))}
              valueLabel={(v) => `${v} views`}
              emptyText="No pages visited."
            />
          </Card>
          {workspaces && (
            <Card title="Workspaces used">
              {data.workspaces_used.length === 0 ? (
                <EmptyBlock>No workspaces.</EmptyBlock>
              ) : (
                <ul className="space-y-1.5">
                  {data.workspaces_used.map((w) => (
                    <li key={w.id} className="flex items-center gap-2 border border-border/60 px-3 py-2 text-sm">
                      <Layers size={13} className="text-primary" />
                      <span className="font-medium text-foreground">{w.name}</span>
                      <span className="ml-auto truncate text-xs text-muted-foreground">{w.id}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
        </div>

        <div className="lg:col-span-3">
          <Card title="Session timeline" subtitle="Click a session to see its events">
            {data.sessions.length === 0 ? (
              <EmptyBlock>No sessions.</EmptyBlock>
            ) : (
              <ul className="-mx-5 -my-5 divide-y divide-border/50">
                {data.sessions.map((s) => {
                  const expanded = expandedSession === s.session_id;
                  const events = eventsBySession.get(s.session_id) ?? [];
                  return (
                    <li key={s.session_id}>
                      <button
                        type="button"
                        aria-expanded={expanded}
                        onClick={() => setExpandedSession(expanded ? null : s.session_id)}
                        className={cn(
                          'flex w-full items-center gap-3 px-5 py-3 text-left text-sm transition-colors hover:bg-muted/40',
                          expanded && 'bg-muted/40'
                        )}
                      >
                        <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold tabular-nums text-primary">
                          {s.events}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-foreground">{formatDateTime(s.started_at, timeZone)}</div>
                          <div className="text-xs text-muted-foreground">
                            {workspaces && `${s.workspace_name ?? '—'} · `}
                            {formatDuration(s.duration_seconds)} · {s.page_views} page views
                          </div>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {[s.device, s.browser].filter(Boolean).join(' · ')}
                        </span>
                      </button>
                      {expanded && (
                        <ul className="bg-muted/20 py-2">
                          {events.length === 0 ? (
                            <li className="px-5 py-2 text-xs text-muted-foreground">No events for this session in the period.</li>
                          ) : (
                            events
                              .slice()
                              .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
                              .map((e) => (
                                <li key={e.event_id} className="flex items-center gap-3 px-5 py-1.5 text-xs">
                                  <EventIcon name={e.event_name} size={11} />
                                  <span className="font-medium text-foreground">{formatEventName(e.event_name)}</span>
                                  {e.page_path && <span className="truncate text-muted-foreground">{e.page_path}</span>}
                                  <span className="ml-auto text-muted-foreground">{formatTime(e.timestamp, timeZone)}</span>
                                </li>
                              ))
                          )}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <Card title="Event history" subtitle={`${data.events.length} event(s)`}>
        <ul className="-mx-5 -my-5 divide-y divide-border/50">
          {data.events.slice(0, HISTORY_SHOWN).map((e) => (
            <li key={e.event_id} className="flex items-start gap-3 px-5 py-2.5 text-sm">
              <EventIcon name={e.event_name} />
              <div className="min-w-0 flex-1">
                <div className="font-medium text-foreground">{formatEventName(e.event_name)}</div>
                <div className="text-xs text-muted-foreground">
                  {e.page_path ?? ''} {workspaces && e.workspace_name ? `· ${e.workspace_name}` : ''}
                </div>
              </div>
              <span className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(e.timestamp, timeZone)}</span>
            </li>
          ))}
        </ul>
        {data.events.length > HISTORY_SHOWN && (
          <div className="mt-3 text-center text-xs text-muted-foreground">
            Showing the first {HISTORY_SHOWN} of {data.events.length} events.
          </div>
        )}
      </Card>
    </div>
  );
}
