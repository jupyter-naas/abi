'use client';

import { Activity, Clock, Eye, Globe, Layers, Repeat, TrendingUp, Users } from 'lucide-react';
import { BarList, type BarItem } from '../bar-list';
import { Card } from '../card';
import { EventIcon, formatEventName } from '../event-icon';
import { formatDateTime, formatDuration, formatNumber } from '../format';
import { KpiCard } from '../kpi-card';
import { LineChart } from '../line-chart';
import { scopeHasWorkspaces } from '../scope';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import type { AnalyticsTabProps } from '../tabs';
import type { AnalyticsEvent, OverviewResponse } from '../types';

/** Per hour or per day, as the period's buckets are. */
export function perBucket(granularity: 'hour' | 'day'): string {
  return granularity === 'hour' ? 'per hour' : 'per day';
}

export function OverviewTab({ scope, filters, timeZone, granularity, onUserPick }: AnalyticsTabProps) {
  const { data, loading, error } = useAnalytics<OverviewResponse>(scope, '/overview', filters);

  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!data) return null;

  const k = data.kpi;
  const isEmpty = k.total_sessions === 0;
  const buckets = data.period?.granularity ?? granularity;
  const workspaces = scopeHasWorkspaces(scope);

  return (
    <div className="space-y-6">
      <div className={workspaces ? 'grid grid-cols-2 gap-4 md:grid-cols-4' : 'grid grid-cols-2 gap-4 md:grid-cols-3'}>
        <KpiCard label="Active users" value={formatNumber(k.active_users)} icon={Users} />
        <KpiCard label="Sessions" value={formatNumber(k.total_sessions)} icon={Activity} />
        <KpiCard label="Avg. sessions / user" value={k.avg_sessions_per_user.toFixed(1)} icon={Repeat} />
        <KpiCard label="Page views" value={formatNumber(k.total_page_views)} icon={Eye} />
        <KpiCard label="Avg. session duration" value={formatDuration(k.avg_session_duration_seconds)} icon={Clock} />
        <KpiCard label="Returning users" value={formatNumber(k.returning_users)} icon={TrendingUp} />
        {workspaces && (
          <>
            <KpiCard label="Workspaces used" value={formatNumber(k.workspaces_used)} icon={Layers} />
            <KpiCard
              label="Most active workspace"
              value={k.most_active_workspace?.name ?? '—'}
              hint={k.most_active_workspace ? `${formatNumber(k.most_active_workspace.events)} events` : undefined}
              icon={Globe}
            />
          </>
        )}
      </div>

      {isEmpty ? (
        <Card title="No activity in this period">
          <EmptyBlock>Try another period or remove the filters.</EmptyBlock>
        </Card>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Sessions over time" subtitle={`Distinct sessions ${perBucket(buckets)}`}>
              <LineChart data={data.sessions_over_time} granularity={buckets} label="sessions" />
            </Card>
            <Card title="Active users over time" subtitle={`Users with at least one event ${perBucket(buckets)}`}>
              <LineChart data={data.active_users_over_time} granularity={buckets} label="users" />
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Top users by activity" subtitle="Click a user to see their activity">
              <BarList
                items={data.top_users.map<BarItem>((u) => ({
                  key: u.user_id,
                  label: u.user_email,
                  sublabel: `${u.sessions} sessions · ${u.page_views} views`,
                  value: u.total_events,
                }))}
                onItemClick={(item) => onUserPick(item.key)}
                valueLabel={(v) => `${formatNumber(v)} events`}
              />
            </Card>
            <Card title="Most viewed pages">
              <BarList
                items={data.top_pages.map<BarItem>((p) => ({
                  key: p.page_path,
                  label: p.page_title,
                  sublabel: p.page_path,
                  value: p.views,
                }))}
                valueLabel={(v) => `${formatNumber(v)} views`}
              />
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            {workspaces && (
              <div className="lg:col-span-2">
                <Card title="Workspace activity">
                  <BarList
                    items={data.workspace_activity.map<BarItem>((w) => ({
                      key: w.workspace_id,
                      label: w.workspace_name,
                      sublabel: `${w.active_users} users · ${w.sessions} sessions`,
                      value: w.events,
                    }))}
                    valueLabel={(v) => `${formatNumber(v)} events`}
                  />
                </Card>
              </div>
            )}
            <div className={workspaces ? 'lg:col-span-3' : 'lg:col-span-5'}>
              <Card title="Recent activity" subtitle="Most recent events of the members">
                <RecentActivityList events={data.recent_activity} timeZone={timeZone} onUserPick={onUserPick} />
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function RecentActivityList({
  events,
  timeZone,
  onUserPick,
}: {
  events: AnalyticsEvent[];
  timeZone: string;
  onUserPick: (userId: string) => void;
}) {
  if (events.length === 0) return <EmptyBlock>No recent events.</EmptyBlock>;
  const sorted = events.slice().sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  return (
    <ul className="-mx-5 -my-5 divide-y divide-border/50">
      {sorted.map((e) => (
        <li key={e.event_id} className="flex items-start gap-3 px-5 py-2.5 text-sm">
          <EventIcon name={e.event_name} />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline gap-2">
              <span className="truncate font-medium text-foreground">{formatEventName(e.event_name)}</span>
              {e.page_path && <span className="truncate text-xs text-muted-foreground">{e.page_path}</span>}
            </div>
            <div className="text-xs text-muted-foreground">
              {e.user_id ? (
                <button
                  type="button"
                  onClick={() => onUserPick(e.user_id as string)}
                  className="hover:text-foreground hover:underline"
                >
                  {e.user_email ?? e.user_id}
                </button>
              ) : (
                <span>{e.user_email ?? 'anonymous'}</span>
              )}
              {e.workspace_name && <span> · {e.workspace_name}</span>}
            </div>
          </div>
          <span className="flex-shrink-0 whitespace-nowrap text-xs text-muted-foreground">
            {formatDateTime(e.timestamp, timeZone)}
          </span>
        </li>
      ))}
    </ul>
  );
}
