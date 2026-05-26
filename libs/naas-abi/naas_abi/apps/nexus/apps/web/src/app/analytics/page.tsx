'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Clock,
  Eye,
  FileText,
  Globe,
  Layers,
  Loader2,
  Mouse,
  Repeat,
  TrendingUp,
  Users,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Avatar, FilterBar, type FilterValue } from './components/filter-bar';
import { KpiCard } from './components/kpi-card';
import { LineChart } from './components/line-chart';
import { BarList, type BarItem } from './components/bar-list';
import { Card } from './components/card';
import { EventIcon, formatEventName } from './components/event-icon';
import { UpdateStatus } from './components/update-status';
import { formatDateTime, formatDuration, formatNumber, formatRelative } from './lib/format';
import { getApiUrl } from '@/lib/config';
import type {
  AnalyticsEvent,
  OverviewResponse,
  PageRow,
  SessionRow,
  UserDetail,
  UserRow,
  WorkspaceRow,
} from './lib/types';

type Tab = 'overview' | 'users' | 'sessions' | 'pages' | 'workspaces' | 'events';

const TABS: { key: Tab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'users', label: 'Users' },
  { key: 'sessions', label: 'Sessions' },
  { key: 'pages', label: 'Pages' },
  { key: 'workspaces', label: 'Workspaces' },
  { key: 'events', label: 'Events' },
];

function initialFilters(): FilterValue {
  const end = new Date();
  const start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000);
  return {
    range: '7d',
    start_date: start.toISOString(),
    end_date: end.toISOString(),
    user_email: 'all',
    workspace_id: 'all',
  };
}

function buildQuery(filters: FilterValue): string {
  const p = new URLSearchParams();
  if (filters.start_date) p.set('start_date', filters.start_date);
  if (filters.end_date) p.set('end_date', filters.end_date);
  if (filters.user_email && filters.user_email !== 'all') p.set('user_email', filters.user_email);
  if (filters.workspace_id && filters.workspace_id !== 'all') p.set('workspace_id', filters.workspace_id);
  return p.toString();
}

interface UsersDirectory {
  users: UserRow[];
  directory: { user_email: string; user_id: string; workspace_ids: string[] }[];
}

interface WorkspacesDirectory {
  workspaces: WorkspaceRow[];
  directory: { workspace_id: string; workspace_name: string }[];
}

export default function AnalyticsPage() {
  const [filters, setFilters] = useState<FilterValue>(initialFilters);
  const [tab, setTab] = useState<Tab>('overview');

  const [usersDir, setUsersDir] = useState<{ user_email: string; user_id: string; workspace_ids: string[] }[]>([]);
  const [workspaceDir, setWorkspaceDir] = useState<{ workspace_id: string; workspace_name: string }[]>([]);

  // Bootstrap directories (independent of date filter — full catalog).
  useEffect(() => {
    const api = getApiUrl();
    fetch(`${api}/api/analytics/users`)
      .then((r) => r.json())
      .then((d: UsersDirectory) => setUsersDir(d.directory ?? []))
      .catch(() => setUsersDir([]));
    fetch(`${api}/api/analytics/workspaces`)
      .then((r) => r.json())
      .then((d: WorkspacesDirectory) => setWorkspaceDir(d.directory ?? []))
      .catch(() => setWorkspaceDir([]));
  }, []);

  const handleUserPick = useCallback((email: string) => {
    setFilters((f) => ({ ...f, user_email: email }));
    setTab('users');
  }, []);

  const isUserDetail = filters.user_email !== 'all';

  // Only Overview and Events are meaningful in user-detail mode.
  const visibleTabs = isUserDetail
    ? TABS.filter((t) => t.key === 'overview' || t.key === 'events')
    : TABS;

  // If the user picks a specific email while on a now-hidden tab, snap back.
  useEffect(() => {
    if (isUserDetail && tab !== 'overview' && tab !== 'events') {
      setTab('overview');
    }
  }, [isUserDetail, tab]);

  const filteredUsersDir =
    filters.workspace_id && filters.workspace_id !== 'all'
      ? usersDir.filter((u) => u.workspace_ids.includes(filters.workspace_id))
      : usersDir;

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-border/60 bg-background/85 backdrop-blur">
        <div className="mx-auto max-w-7xl px-6 py-4">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-workspace-accent">
                Nexus Analytics
              </p>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight">
                {isUserDetail ? (
                  <span className="flex items-center gap-3">
                    <Avatar email={filters.user_email} size={32} />
                    <span>{filters.user_email}</span>
                  </span>
                ) : (
                  'Platform usage'
                )}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {isUserDetail
                  ? 'Detailed activity for the selected user.'
                  : 'How your users are engaging across sessions, pages, and workspaces.'}
              </p>
            </div>
            <UpdateStatus />
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <FilterBar
              value={filters}
              onChange={setFilters}
              users={filteredUsersDir}
              workspaces={workspaceDir}
            />
            <nav className="flex items-center border border-border/60 bg-card">
              {visibleTabs.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={cn(
                    'px-3 py-1.5 text-sm font-medium transition-colors border-r border-border/60 last:border-r-0',
                    tab === t.key
                      ? 'bg-workspace-accent text-white'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )}
                >
                  {t.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {isUserDetail && tab !== 'events' && tab !== 'overview' ? (
          <UserDetailSection filters={filters} onClear={() => setFilters({ ...filters, user_email: 'all' })} />
        ) : null}

        {tab === 'overview' &&
          (isUserDetail ? (
            <UserDetailSection filters={filters} onClear={() => setFilters({ ...filters, user_email: 'all' })} />
          ) : (
            <OverviewSection filters={filters} onUserPick={handleUserPick} />
          ))}

        {tab === 'users' && !isUserDetail && (
          <UsersSection filters={filters} onUserPick={handleUserPick} />
        )}

        {tab === 'sessions' && !isUserDetail && <SessionsSection filters={filters} />}
        {tab === 'pages' && !isUserDetail && <PagesSection filters={filters} />}
        {tab === 'workspaces' && !isUserDetail && <WorkspacesSection filters={filters} />}
        {tab === 'events' && <EventsSection filters={filters} />}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generic fetch hook
// ---------------------------------------------------------------------------

function useAnalytics<T>(
  path: string,
  filters: FilterValue,
  extra?: Record<string, string>,
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const extraKey = extra ? JSON.stringify(extra) : '';

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const p = new URLSearchParams(buildQuery(filters));
    if (extra) {
      Object.entries(extra).forEach(([k, v]) => p.set(k, v));
    }
    const qs = p.toString();
    const url = `${getApiUrl()}${path}${qs ? `?${qs}` : ''}`;

    fetch(url)
      .then(async (r) => {
        if (!r.ok) throw new Error(`Request failed (${r.status})`);
        return r.json();
      })
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e?.message ?? e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, buildQuery(filters), extraKey]);

  return { data, loading, error };
}

function LoadingBlock({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-20 text-sm text-muted-foreground">
      <Loader2 size={16} className="animate-spin" />
      {label}…
    </div>
  );
}

function ErrorBlock({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center gap-2 border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
      <AlertTriangle size={16} />
      {message}
    </div>
  );
}

function EmptyBlock({ children }: { children: React.ReactNode }) {
  return (
    <div className="py-16 text-center">
      <p className="text-sm text-muted-foreground">{children}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview (All Users)
// ---------------------------------------------------------------------------

function OverviewSection({
  filters,
  onUserPick,
}: {
  filters: FilterValue;
  onUserPick: (email: string) => void;
}) {
  const { data, loading, error } = useAnalytics<OverviewResponse>('/api/analytics/overview', filters);

  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!data) return null;

  const k = data.kpi;
  const isEmpty = k.total_sessions === 0;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
        <KpiCard label="Active users" value={formatNumber(k.active_users)} icon={Users} />
        <KpiCard label="Sessions" value={formatNumber(k.total_sessions)} icon={Activity} />
        <KpiCard
          label="Avg. sessions / user"
          value={k.avg_sessions_per_user.toFixed(1)}
          icon={Repeat}
        />
        <KpiCard label="Page views" value={formatNumber(k.total_page_views)} icon={Eye} />
        <KpiCard label="Workspaces used" value={formatNumber(k.workspaces_used)} icon={Layers} />
        <KpiCard
          label="Avg. session duration"
          value={formatDuration(k.avg_session_duration_seconds)}
          icon={Clock}
        />
        <KpiCard label="Returning users" value={formatNumber(k.returning_users)} icon={TrendingUp} />
        <KpiCard
          label="Most active workspace"
          value={k.most_active_workspace?.name ?? '—'}
          hint={
            k.most_active_workspace
              ? `${formatNumber(k.most_active_workspace.events)} events`
              : undefined
          }
          icon={Globe}
        />
      </div>

      {isEmpty ? (
        <Card title="No activity in this period">
          <EmptyBlock>Try widening the date range or removing filters.</EmptyBlock>
        </Card>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Sessions over time" subtitle="Distinct sessions per day">
              <LineChart data={data.sessions_over_time} label="sessions" />
            </Card>
            <Card
              title="Active users over time"
              subtitle="Unique users with at least one event per day"
            >
              <LineChart
                data={data.active_users_over_time}
                label="users"
              />
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Top users by activity" subtitle="Click an email to drill down">
              <BarList
                items={data.top_users.map<BarItem>((u) => ({
                  key: u.user_email,
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
            <div className="lg:col-span-3">
              <Card title="Recent activity" subtitle="Most recent events across all users">
                <RecentActivityList events={data.recent_activity} onUserPick={onUserPick} />
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
  onUserPick,
}: {
  events: AnalyticsEvent[];
  onUserPick: (email: string) => void;
}) {
  if (events.length === 0) return <EmptyBlock>No recent events.</EmptyBlock>;
  const sorted = events.slice().sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  return (
    <ul className="divide-y divide-border/50 -mx-5 -my-5">
      {sorted.map((e) => (
        <li key={e.event_id} className="flex items-start gap-3 px-5 py-2.5 text-sm">
          <EventIcon name={e.event_name} />
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="font-medium truncate">{formatEventName(e.event_name)}</span>
              {e.page_path && (
                <span className="text-xs text-muted-foreground truncate">{e.page_path}</span>
              )}
            </div>
            <div className="text-xs text-muted-foreground">
              <button
                onClick={() => e.user_email && onUserPick(e.user_email)}
                className="hover:text-foreground hover:underline"
              >
                {e.user_email ?? 'anonymous'}
              </button>
              {e.workspace_name && (
                <>
                  {' · '}
                  <span>{e.workspace_name}</span>
                </>
              )}
            </div>
          </div>
          <span className="flex-shrink-0 text-xs text-muted-foreground whitespace-nowrap">
            {formatDateTime(e.timestamp)}
          </span>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Users (All Users tab)
// ---------------------------------------------------------------------------

function UsersSection({
  filters,
  onUserPick,
}: {
  filters: FilterValue;
  onUserPick: (email: string) => void;
}) {
  const { data, loading, error } = useAnalytics<UsersDirectory>('/api/analytics/users', filters);
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!data) return null;
  if (data.users.length === 0)
    return (
      <Card title="No users">
        <EmptyBlock>No user activity in the selected period.</EmptyBlock>
      </Card>
    );
  return (
    <Card title="Users" subtitle="Click a row to see that user's detail">
      <div className="-mx-5 -my-5">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border/60">
              <th className="px-5 py-3 font-medium">User</th>
              <th className="px-5 py-3 font-medium text-right">Sessions</th>
              <th className="px-5 py-3 font-medium text-right">Page views</th>
              <th className="px-5 py-3 font-medium text-right">Workspaces</th>
              <th className="px-5 py-3 font-medium text-right">Events</th>
              <th className="px-5 py-3 font-medium text-right">Last seen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {data.users.map((u) => (
              <tr
                key={u.user_email}
                className="cursor-pointer transition-colors hover:bg-muted/40"
                onClick={() => onUserPick(u.user_email)}
              >
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2.5">
                    <Avatar email={u.user_email} size={26} />
                    <span className="font-medium">{u.user_email}</span>
                  </div>
                </td>
                <td className="px-5 py-3 text-right tabular-nums">{u.sessions}</td>
                <td className="px-5 py-3 text-right tabular-nums">{u.page_views}</td>
                <td className="px-5 py-3 text-right tabular-nums">{u.workspaces}</td>
                <td className="px-5 py-3 text-right tabular-nums">{u.total_events}</td>
                <td className="px-5 py-3 text-right text-muted-foreground">
                  {formatRelative(u.last_seen)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

function SessionsSection({ filters }: { filters: FilterValue }) {
  const { data, loading, error } = useAnalytics<{ sessions: SessionRow[] }>(
    '/api/analytics/sessions',
    filters,
  );
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  const sessions = data?.sessions ?? [];
  return (
    <Card title="Sessions" subtitle={`${sessions.length.toLocaleString()} session(s) in this range`}>
      <div className="-mx-5 -my-5">
        {sessions.length === 0 ? (
          <EmptyBlock>No sessions match these filters.</EmptyBlock>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground border-b border-border/60">
                <th className="px-5 py-3 font-medium">User</th>
                <th className="px-5 py-3 font-medium">Workspace</th>
                <th className="px-5 py-3 font-medium">Started</th>
                <th className="px-5 py-3 font-medium text-right">Duration</th>
                <th className="px-5 py-3 font-medium text-right">Page views</th>
                <th className="px-5 py-3 font-medium text-right">Events</th>
                <th className="px-5 py-3 font-medium">Device</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {sessions.slice(0, 200).map((s) => (
                <tr key={s.session_id} className="transition-colors hover:bg-muted/40">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <Avatar email={s.user_email} size={22} />
                      <span className="truncate">{s.user_email}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-muted-foreground">{s.workspace_name ?? '—'}</td>
                  <td className="px-5 py-3 text-muted-foreground">{formatDateTime(s.started_at)}</td>
                  <td className="px-5 py-3 text-right tabular-nums">
                    {formatDuration(s.duration_seconds)}
                  </td>
                  <td className="px-5 py-3 text-right tabular-nums">{s.page_views}</td>
                  <td className="px-5 py-3 text-right tabular-nums">{s.events}</td>
                  <td className="px-5 py-3 text-muted-foreground">
                    {[s.device, s.browser].filter(Boolean).join(' · ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {sessions.length > 200 && (
          <div className="px-5 py-3 text-xs text-muted-foreground border-t border-border/50">
            Showing first 200 of {sessions.length.toLocaleString()} sessions.
          </div>
        )}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------------

function PagesSection({ filters }: { filters: FilterValue }) {
  const { data, loading, error } = useAnalytics<{ pages: PageRow[] }>(
    '/api/analytics/pages',
    filters,
  );
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  const pages = data?.pages ?? [];
  return (
    <Card title="Pages" subtitle="Page views and unique visitors">
      {pages.length === 0 ? (
        <EmptyBlock>No page views in this range.</EmptyBlock>
      ) : (
        <BarList
          items={pages.map((p) => ({
            key: p.page_path,
            label: p.page_title,
            sublabel: `${p.page_path} · ${p.unique_users} unique users`,
            value: p.views,
          }))}
          valueLabel={(v) => `${formatNumber(v)} views`}
        />
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Workspaces
// ---------------------------------------------------------------------------

function WorkspacesSection({ filters }: { filters: FilterValue }) {
  const { data, loading, error } = useAnalytics<WorkspacesDirectory>(
    '/api/analytics/workspaces',
    filters,
  );
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  const ws = data?.workspaces ?? [];
  return (
    <Card title="Workspaces" subtitle="Activity per workspace in the selected period">
      {ws.length === 0 ? (
        <EmptyBlock>No workspace activity.</EmptyBlock>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
          {ws.map((w) => (
            <div
              key={w.workspace_id}
              className="border border-border/60 bg-background p-4"
            >
              <div className="flex items-center gap-2">
                <Layers size={14} className="text-workspace-accent" />
                <h4 className="font-medium truncate">{w.workspace_name}</h4>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-xl font-semibold tabular-nums">{w.active_users}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Users</p>
                </div>
                <div>
                  <p className="text-xl font-semibold tabular-nums">{w.sessions}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Sessions</p>
                </div>
                <div>
                  <p className="text-xl font-semibold tabular-nums">{formatNumber(w.events)}</p>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Events</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

function EventsSection({ filters }: { filters: FilterValue }) {
  const { data, loading, error } = useAnalytics<{ events: AnalyticsEvent[] }>(
    '/api/analytics/events',
    filters,
    { limit: '300' },
  );
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  const events = data?.events ?? [];
  return (
    <Card title="Event stream" subtitle="Most recent events match the current filters">
      {events.length === 0 ? (
        <EmptyBlock>No events in this range.</EmptyBlock>
      ) : (
        <ul className="-mx-5 -my-5 divide-y divide-border/50">
          {events.map((e) => (
            <li key={e.event_id} className="flex items-start gap-3 px-5 py-3 text-sm">
              <EventIcon name={e.event_name} />
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="font-medium">{formatEventName(e.event_name)}</span>
                  {e.page_path && (
                    <span className="text-xs text-muted-foreground">{e.page_path}</span>
                  )}
                  {e.properties && (
                    <span className="text-xs text-muted-foreground font-mono">
                      {JSON.stringify(e.properties)}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                  <span>{e.user_email ?? 'anonymous'}</span>
                  {e.workspace_name && <span>· {e.workspace_name}</span>}
                  {e.device && <span>· {e.device}</span>}
                  {e.browser && <span>· {e.browser}</span>}
                  {e.country && <span>· {e.country}</span>}
                </div>
              </div>
              <div className="flex-shrink-0 text-right text-xs text-muted-foreground whitespace-nowrap">
                <div>{formatDateTime(e.timestamp)}</div>
                <div className="font-mono opacity-70">{e.session_id.slice(0, 12)}</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// User detail
// ---------------------------------------------------------------------------

function UserDetailSection({
  filters,
  onClear,
}: {
  filters: FilterValue;
  onClear: () => void;
}) {
  const path = `/api/analytics/users/${encodeURIComponent(filters.user_email)}`;
  const { data, loading, error } = useAnalytics<UserDetail>(path, filters);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);

  if (loading && !data) return <LoadingBlock />;
  if (error)
    return (
      <Card
        title="Could not load user"
        action={
          <button
            onClick={onClear}
            className="text-xs text-workspace-accent hover:underline"
          >
            Clear user filter
          </button>
        }
      >
        <EmptyBlock>{error}</EmptyBlock>
      </Card>
    );
  if (!data) return null;

  const eventsBySession = new Map<string, AnalyticsEvent[]>();
  for (const e of data.events) {
    const list = eventsBySession.get(e.session_id) ?? [];
    list.push(e);
    eventsBySession.set(e.session_id, list);
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
        <KpiCard label="First seen" value={formatRelative(data.first_seen)} hint={formatDateTime(data.first_seen)} icon={Clock} />
        <KpiCard label="Last seen" value={formatRelative(data.last_seen)} hint={formatDateTime(data.last_seen)} icon={Activity} />
        <KpiCard label="Total sessions" value={data.total_sessions} icon={Repeat} />
        <KpiCard label="Page views" value={data.total_page_views} icon={Eye} />
        <KpiCard label="Workspaces used" value={data.workspaces_used.length} icon={Layers} />
        <KpiCard
          label="Most visited page"
          value={data.most_visited_page?.title ?? '—'}
          hint={data.most_visited_page ? `${data.most_visited_page.views} views` : undefined}
          icon={FileText}
        />
        <KpiCard label="User ID" value={data.user_id || '—'} icon={Mouse} />
        <KpiCard
          label="Workspaces"
          value={data.workspaces_used.length}
          hint={data.workspaces_used.map((w) => w.name).join(', ') || '—'}
          icon={BarChart3}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2 space-y-6">
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
          <Card title="Workspaces used">
            {data.workspaces_used.length === 0 ? (
              <EmptyBlock>No workspaces.</EmptyBlock>
            ) : (
              <ul className="space-y-1.5">
                {data.workspaces_used.map((w) => (
                  <li
                    key={w.id}
                    className="flex items-center gap-2 border border-border/60 px-3 py-2 text-sm"
                  >
                    <Layers size={13} className="text-workspace-accent" />
                    <span className="font-medium">{w.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">{w.id}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
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
                        onClick={() =>
                          setExpandedSession(expanded ? null : s.session_id)
                        }
                        className={cn(
                          'flex w-full items-center gap-3 px-5 py-3 text-left text-sm transition-colors',
                          'hover:bg-muted/40',
                          expanded && 'bg-muted/40',
                        )}
                      >
                        <span
                          className={cn(
                            'flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full',
                            'bg-workspace-accent-10 text-workspace-accent text-xs font-semibold tabular-nums',
                          )}
                        >
                          {s.events}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-foreground">
                            {formatDateTime(s.started_at)}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {s.workspace_name ?? '—'} ·{' '}
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
                            <li className="px-5 py-2 text-xs text-muted-foreground">
                              No events for this session in range.
                            </li>
                          ) : (
                            events
                              .slice()
                              .sort((a, b) => a.timestamp.localeCompare(b.timestamp))
                              .map((e) => (
                                <li
                                  key={e.event_id}
                                  className="flex items-center gap-3 px-5 py-1.5 text-xs"
                                >
                                  <EventIcon name={e.event_name} size={11} />
                                  <span className="font-medium">{formatEventName(e.event_name)}</span>
                                  {e.page_path && (
                                    <span className="text-muted-foreground truncate">
                                      {e.page_path}
                                    </span>
                                  )}
                                  <span className="ml-auto text-muted-foreground">
                                    {new Date(e.timestamp).toLocaleTimeString(undefined, {
                                      hour: '2-digit',
                                      minute: '2-digit',
                                      second: '2-digit',
                                    })}
                                  </span>
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

      <Card title="Chronological event history" subtitle={`${data.events.length} event(s)`}>
        <ul className="-mx-5 -my-5 divide-y divide-border/50">
          {data.events.slice(0, 100).map((e) => (
            <li key={e.event_id} className="flex items-start gap-3 px-5 py-2.5 text-sm">
              <EventIcon name={e.event_name} />
              <div className="flex-1 min-w-0">
                <div className="font-medium">{formatEventName(e.event_name)}</div>
                <div className="text-xs text-muted-foreground">
                  {e.page_path ?? ''} {e.workspace_name ? `· ${e.workspace_name}` : ''}
                </div>
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {formatDateTime(e.timestamp)}
              </span>
            </li>
          ))}
        </ul>
        {data.events.length > 100 && (
          <div className="mt-3 text-xs text-muted-foreground text-center">
            Showing first 100 of {data.events.length} events.
          </div>
        )}
      </Card>
    </div>
  );
}
