import type {
  AnalyticsEvent,
  AnalyticsFilters,
  OverviewKpi,
  OverviewResponse,
  PageRow,
  SessionRow,
  TimeseriesPoint,
  UserDetail,
  UserRow,
  WorkspaceRow,
} from './types';

export function applyFilters(events: AnalyticsEvent[], filters: AnalyticsFilters): AnalyticsEvent[] {
  return events.filter((e) => {
    if (filters.start_date && e.timestamp < filters.start_date) return false;
    if (filters.end_date && e.timestamp > filters.end_date) return false;
    if (filters.user_email && filters.user_email !== 'all' && e.user_email !== filters.user_email) return false;
    if (filters.workspace_id && filters.workspace_id !== 'all' && e.workspace_id !== filters.workspace_id) return false;
    return true;
  });
}

function dayKey(ts: string): string {
  return ts.slice(0, 10);
}

function rangeDays(filters: AnalyticsFilters): string[] {
  const end = filters.end_date ? new Date(filters.end_date) : new Date();
  const start = filters.start_date
    ? new Date(filters.start_date)
    : new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);
  const out: string[] = [];
  const cursor = new Date(start);
  cursor.setUTCHours(0, 0, 0, 0);
  const endDay = new Date(end);
  endDay.setUTCHours(0, 0, 0, 0);
  while (cursor.getTime() <= endDay.getTime()) {
    out.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return out;
}

function groupBy<T, K extends string>(arr: T[], keyFn: (x: T) => K): Map<K, T[]> {
  const m = new Map<K, T[]>();
  for (const x of arr) {
    const k = keyFn(x);
    const list = m.get(k);
    if (list) list.push(x);
    else m.set(k, [x]);
  }
  return m;
}

interface SessionAgg {
  session_id: string;
  user_id?: string;
  user_email?: string;
  workspace_id?: string;
  workspace_name?: string;
  started_at: string;
  ended_at: string;
  page_views: number;
  events: number;
  device?: string;
  browser?: string;
}

function buildSessions(events: AnalyticsEvent[]): SessionAgg[] {
  const sessions = groupBy(events, (e) => e.session_id as string);
  const out: SessionAgg[] = [];
  sessions.forEach((evts, session_id) => {
    evts.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    const first = evts[0];
    const last = evts[evts.length - 1];
    out.push({
      session_id,
      user_id: first.user_id,
      user_email: first.user_email,
      workspace_id: first.workspace_id,
      workspace_name: first.workspace_name,
      started_at: first.timestamp,
      ended_at: last.timestamp,
      page_views: evts.filter((e) => e.event_name === 'page_viewed').length,
      events: evts.length,
      device: first.device,
      browser: first.browser,
    });
  });
  out.sort((a, b) => b.started_at.localeCompare(a.started_at));
  return out;
}

function sessionDurationSec(s: SessionAgg): number {
  return Math.max(0, Math.floor((new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()) / 1000));
}

export function computeOverview(events: AnalyticsEvent[], filters: AnalyticsFilters): OverviewResponse {
  const days = rangeDays(filters);
  const sessions = buildSessions(events);
  const pageViews = events.filter((e) => e.event_name === 'page_viewed');

  const activeUserSet = new Set(events.map((e) => e.user_email).filter(Boolean));
  const workspaceSet = new Set(events.map((e) => e.workspace_id).filter(Boolean));

  const sessionsByUser = groupBy(sessions, (s) => (s.user_email ?? 'unknown') as string);
  const totalDurationSec = sessions.reduce((s, x) => s + sessionDurationSec(x), 0);
  const avgSessionDuration = sessions.length ? Math.floor(totalDurationSec / sessions.length) : 0;
  const returningUsers = Array.from(sessionsByUser.values()).filter((arr) => arr.length > 1).length;

  const wsEventCounts = new Map<string, { id: string; name: string; events: number }>();
  for (const e of events) {
    if (!e.workspace_id) continue;
    const cur = wsEventCounts.get(e.workspace_id);
    if (cur) cur.events += 1;
    else wsEventCounts.set(e.workspace_id, { id: e.workspace_id, name: e.workspace_name ?? e.workspace_id, events: 1 });
  }
  const mostActiveWorkspace =
    Array.from(wsEventCounts.values()).sort((a, b) => b.events - a.events)[0] ?? null;

  const kpi: OverviewKpi = {
    active_users: activeUserSet.size,
    total_sessions: sessions.length,
    avg_sessions_per_user: activeUserSet.size
      ? Math.round((sessions.length / activeUserSet.size) * 10) / 10
      : 0,
    total_page_views: pageViews.length,
    workspaces_used: workspaceSet.size,
    avg_session_duration_seconds: avgSessionDuration,
    returning_users: returningUsers,
    most_active_workspace: mostActiveWorkspace,
  };

  const sessionsByDay = new Map<string, Set<string>>();
  for (const s of sessions) {
    const k = dayKey(s.started_at);
    const set = sessionsByDay.get(k) ?? new Set();
    set.add(s.session_id);
    sessionsByDay.set(k, set);
  }
  const sessions_over_time: TimeseriesPoint[] = days.map((d) => ({
    date: d,
    value: sessionsByDay.get(d)?.size ?? 0,
  }));

  const usersByDay = new Map<string, Set<string>>();
  for (const e of events) {
    if (!e.user_email) continue;
    const k = dayKey(e.timestamp);
    const set = usersByDay.get(k) ?? new Set();
    set.add(e.user_email);
    usersByDay.set(k, set);
  }
  const active_users_over_time: TimeseriesPoint[] = days.map((d) => ({
    date: d,
    value: usersByDay.get(d)?.size ?? 0,
  }));

  return {
    kpi,
    sessions_over_time,
    active_users_over_time,
    top_users: computeUserRows(events).slice(0, 10),
    top_pages: computePageRows(events).slice(0, 10),
    workspace_activity: computeWorkspaceRows(events),
    recent_activity: [...events].sort((a, b) => b.timestamp.localeCompare(a.timestamp)).slice(0, 25),
  };
}

export function computeUserRows(events: AnalyticsEvent[]): UserRow[] {
  const byUser = groupBy(events.filter((e) => e.user_email), (e) => e.user_email as string);
  const rows: UserRow[] = [];
  byUser.forEach((evts, email) => {
    const sessionIds = new Set(evts.map((e) => e.session_id));
    const workspaces = new Set(evts.map((e) => e.workspace_id).filter(Boolean));
    const pageViews = evts.filter((e) => e.event_name === 'page_viewed').length;
    const last = evts.reduce((a, b) => (a.timestamp > b.timestamp ? a : b));
    rows.push({
      user_id: last.user_id ?? '',
      user_email: email,
      sessions: sessionIds.size,
      page_views: pageViews,
      workspaces: workspaces.size,
      last_seen: last.timestamp,
      total_events: evts.length,
    });
  });
  rows.sort((a, b) => b.total_events - a.total_events);
  return rows;
}

function decoratePageTitle(title: string, path: string): string {
  // Chat conversation pages share the title "Chat" — re-derive the conv
  // suffix from the path so each conversation surfaces as its own row even
  // when stored events predate write-time decoration.
  const m = path.match(/\/chat\/(conv-[^/?#]+)/);
  if (!m) return title;
  const conv = m[1];
  return title.includes(conv) ? title : `${title} - ${conv}`;
}

export function computePageRows(events: AnalyticsEvent[]): PageRow[] {
  const views = events.filter((e) => e.event_name === 'page_viewed' && e.page_path);
  const byPage = groupBy(views, (e) => e.page_path as string);
  const rows: PageRow[] = [];
  byPage.forEach((evts, path) => {
    const uniqueUsers = new Set(evts.map((e) => e.user_email).filter(Boolean));
    rows.push({
      page_path: path,
      page_title: decoratePageTitle(evts[0].page_title ?? path, path),
      views: evts.length,
      unique_users: uniqueUsers.size,
    });
  });
  rows.sort((a, b) => b.views - a.views);
  return rows;
}

export function computeWorkspaceRows(events: AnalyticsEvent[]): WorkspaceRow[] {
  const withWs = events.filter((e) => e.workspace_id);
  const byWs = groupBy(withWs, (e) => e.workspace_id as string);
  const rows: WorkspaceRow[] = [];
  byWs.forEach((evts, wsId) => {
    const sessionIds = new Set(evts.map((e) => e.session_id));
    const users = new Set(evts.map((e) => e.user_email).filter(Boolean));
    rows.push({
      workspace_id: wsId,
      workspace_name: evts[0].workspace_name ?? wsId,
      active_users: users.size,
      sessions: sessionIds.size,
      events: evts.length,
    });
  });
  rows.sort((a, b) => b.events - a.events);
  return rows;
}

export function computeSessionRows(events: AnalyticsEvent[]): SessionRow[] {
  return buildSessions(events).map((s) => ({
    session_id: s.session_id,
    user_email: s.user_email ?? 'unknown',
    workspace_name: s.workspace_name,
    started_at: s.started_at,
    ended_at: s.ended_at,
    duration_seconds: sessionDurationSec(s),
    page_views: s.page_views,
    events: s.events,
    device: s.device,
    browser: s.browser,
  }));
}

export function computeUserDetail(events: AnalyticsEvent[], email: string): UserDetail | null {
  const userEvents = events.filter((e) => e.user_email === email);
  if (userEvents.length === 0) return null;

  const sorted = [...userEvents].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  const first = sorted[0];
  const last = sorted[sorted.length - 1];

  const sessionIds = new Set(sorted.map((e) => e.session_id));
  const pageViews = sorted.filter((e) => e.event_name === 'page_viewed');
  const pages = computePageRows(userEvents);
  const sessions = computeSessionRows(userEvents);

  const workspaceMap = new Map<string, string>();
  for (const e of userEvents) {
    if (e.workspace_id) workspaceMap.set(e.workspace_id, e.workspace_name ?? e.workspace_id);
  }

  return {
    user_email: email,
    user_id: first.user_id ?? '',
    first_seen: first.timestamp,
    last_seen: last.timestamp,
    total_sessions: sessionIds.size,
    total_page_views: pageViews.length,
    workspaces_used: Array.from(workspaceMap.entries()).map(([id, name]) => ({ id, name })),
    most_visited_page: pages[0]
      ? { path: pages[0].page_path, title: pages[0].page_title, views: pages[0].views }
      : null,
    sessions,
    pages,
    events: [...sorted].reverse(),
  };
}
