'use client';

import { useMemo, useState } from 'react';
import {
  Button,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Select,
} from 'react-aria-components';

import { DataTable, type DataTableColumn } from '@/components/dashboard/table/DataTable';
import { KpiCard } from '@/components/dashboard/kpi/KpiCard';
import {
  listBoxItemPage,
  listBoxPage,
  popoverPage,
  selectTriggerPage,
} from '@/lib/ariaStyles';
import type { AnalyticsEvent } from '@/lib/server/analytics';
import type { EntityConfig } from '@/lib/types';

export type EnrichedAnalyticsEvent = AnalyticsEvent & { email: string | null };

type Period = 'today' | 'yesterday' | '7d' | '30d';

const PERIOD_ORDER: Period[] = ['today', 'yesterday', '7d', '30d'];
const PERIOD_LABELS: Record<Period, string> = {
  today: 'Today',
  yesterday: 'Yesterday',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
};

function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return new Intl.DateTimeFormat('en-GB', { dateStyle: 'short', timeStyle: 'short' }).format(d);
}

function startOfDay(d: Date): number {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x.getTime();
}

/** Today/Yesterday use the viewer's local calendar day; 7d/30d are rolling windows. */
function inPeriod(iso: string, period: Period): boolean {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return false;
  const now = new Date();
  const todayStart = startOfDay(now);
  if (period === 'today') return t >= todayStart;
  if (period === 'yesterday') return t >= todayStart - 86_400_000 && t < todayStart;
  if (period === '7d') return t >= now.getTime() - 7 * 86_400_000;
  return t >= now.getTime() - 30 * 86_400_000;
}

function topCounts(entries: string[], limit: number): { label: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const entry of entries) {
    counts.set(entry, (counts.get(entry) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([label, count]) => ({ label, count }));
}

/** Display name for a perimeter slug; falls back to parsing legacy page keys. */
function perimeterLabel(
  event: { perimeter?: string | null; page: string | null },
  entityNameBySlug: Map<string, string>,
): string {
  if (event.perimeter) {
    return entityNameBySlug.get(event.perimeter) ?? event.perimeter;
  }
  const page = event.page;
  if (!page) return '—';
  if (page.startsWith('admin') || page.startsWith('/admin') || page.startsWith('admin:')) {
    return '—';
  }
  // Legacy keys: "/slug/…", "slug/…", or "slug:pageId"
  if (page.includes('/')) {
    const slug = page.replace(/^\//, '').split('/')[0] ?? '';
    return slug ? (entityNameBySlug.get(slug) ?? slug) : '—';
  }
  if (page.includes(':')) {
    const [slug] = page.split(':');
    return slug ? (entityNameBySlug.get(slug) ?? slug) : '—';
  }
  return '—';
}

type Props = {
  events: EnrichedAnalyticsEvent[];
  entities: EntityConfig[];
};

export function AnalyticsDashboard({ events, entities }: Props) {
  const [period, setPeriod] = useState<Period>('7d');
  const [email, setEmail] = useState('all');

  const entityNameBySlug = useMemo(
    () => new Map(entities.map((e) => [e.url_slug, e.display_name])),
    [entities],
  );

  const emailOptions = useMemo(() => {
    const set = new Set<string>();
    for (const e of events) {
      if (e.email) set.add(e.email);
    }
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [events]);

  const filtered = useMemo(
    () =>
      events.filter(
        (e) => inPeriod(e.timestamp, period) && (email === 'all' || e.email === email),
      ),
    [events, period, email],
  );

  const logins = filtered.filter((e) => e.type === 'login');
  const pageviews = filtered.filter((e) => e.type === 'pageview');
  const activeUsers = new Set(filtered.map((e) => e.user_id)).size;

  const recentLogins = useMemo(
    () => [...logins].sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1)).slice(0, 10),
    [logins],
  );

  const topUsers = useMemo(
    () => topCounts(filtered.map((e) => e.email ?? e.name), 5),
    [filtered],
  );
  const topPages = useMemo(
    () => topCounts(pageviews.filter((e) => e.page).map((e) => e.page as string), 5),
    [pageviews],
  );

  const recentPageviews = useMemo(
    () => [...pageviews].sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1)),
    [pageviews],
  );

  const activeUsersColumns: DataTableColumn[] = [
    { key: 'label', label: 'User' },
    { key: 'count', label: 'Activity', align: 'right' },
  ];
  const topPagesColumns: DataTableColumn[] = [
    { key: 'label', label: 'Page' },
    { key: 'count', label: 'Views', align: 'right' },
  ];
  const recentLoginsColumns: DataTableColumn[] = [
    { key: 'date', label: 'Date' },
    { key: 'user', label: 'User' },
  ];
  const pageviewColumns: DataTableColumn[] = [
    { key: 'date', label: 'Date' },
    { key: 'user', label: 'User' },
    { key: 'page', label: 'Page' },
    { key: 'perimeter', label: 'Perimeter' },
  ];

  const recentLoginRecords = recentLogins.map((e) => ({
    date: fmtDateTime(e.timestamp),
    user: e.email ?? e.name,
  }));

  const pageviewRecords = recentPageviews.map((e) => ({
    date: fmtDateTime(e.timestamp),
    user: e.email ?? e.name,
    page: e.page ?? '—',
    perimeter: perimeterLabel(e, entityNameBySlug),
  }));

  const periodLabel = PERIOD_LABELS[period];
  const emailLabel = email === 'all' ? 'All users' : email;

  return (
    <div className="space-y-8">
      <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
        <Select
          aria-label="Filter by period"
          selectedKey={period}
          onSelectionChange={(key) => {
            if (key != null) setPeriod(String(key) as Period);
          }}
          className="w-full max-w-xs"
        >
          <Label className="sr-only">Filter by period</Label>
          <Button className={selectTriggerPage}>
            <span className="truncate uppercase font-semibold tracking-wide text-center w-full !text-white">
              {periodLabel}
            </span>
            <span aria-hidden className="absolute right-4 text-white/80 shrink-0 text-base leading-none">
              ▾
            </span>
          </Button>
          <Popover className={`${popoverPage} min-w-[var(--trigger-width)]`} offset={0}>
            <ListBox selectionMode="single" className={`${listBoxPage} w-full`}>
              {PERIOD_ORDER.map((p) => (
                <ListBoxItem key={p} id={p} textValue={PERIOD_LABELS[p]} className={listBoxItemPage}>
                  {PERIOD_LABELS[p]}
                </ListBoxItem>
              ))}
            </ListBox>
          </Popover>
        </Select>

        <Select
          aria-label="Filter by user"
          selectedKey={email}
          onSelectionChange={(key) => {
            if (key != null) setEmail(String(key));
          }}
          className="w-full max-w-xs"
        >
          <Label className="sr-only">Filter by user</Label>
          <Button className={selectTriggerPage}>
            <span className="truncate uppercase font-semibold tracking-wide text-center w-full !text-white">
              {emailLabel}
            </span>
            <span aria-hidden className="absolute right-4 text-white/80 shrink-0 text-base leading-none">
              ▾
            </span>
          </Button>
          <Popover className={`${popoverPage} min-w-[var(--trigger-width)]`} offset={0}>
            <ListBox selectionMode="single" className={`${listBoxPage} w-full max-h-[min(24rem,70vh)] overflow-y-auto`}>
              <ListBoxItem id="all" textValue="All users" className={listBoxItemPage}>
                All users
              </ListBoxItem>
              {emailOptions.map((em) => (
                <ListBoxItem key={em} id={em} textValue={em} className={listBoxItemPage}>
                  {em}
                </ListBoxItem>
              ))}
            </ListBox>
          </Popover>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard
          label="Sign-ins"
          value={logins.length}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle={PERIOD_LABELS[period]}
        />
        <KpiCard
          label="Active users"
          value={activeUsers}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle={PERIOD_LABELS[period]}
        />
        <KpiCard
          label="Page views"
          value={pageviews.length}
          valueStyle="decimal"
          maximumFractionDigits={0}
          subtitle={PERIOD_LABELS[period]}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div>
          <h2 className="type-title-4 mb-1">Most active users</h2>
          <p className="mb-3 text-xs text-[var(--text-muted)]">
            Sign-ins + page views, {PERIOD_LABELS[period].toLowerCase()}
          </p>
          <DataTable
            records={topUsers}
            columns={activeUsersColumns}
            paginate={false}
            exportable={false}
            emptyMessage="No data yet."
          />
        </div>
        <div>
          <h2 className="type-title-4 mb-1">Most visited pages</h2>
          <p className="mb-3 text-xs text-[var(--text-muted)]">{PERIOD_LABELS[period]}</p>
          <DataTable
            records={topPages}
            columns={topPagesColumns}
            paginate={false}
            exportable={false}
            emptyMessage="No data yet."
          />
        </div>
        <div>
          <h2 className="type-title-4 mb-1">Recent sign-ins</h2>
          <p className="mb-3 text-xs text-[var(--text-muted)]">{PERIOD_LABELS[period]}</p>
          <DataTable
            records={recentLoginRecords}
            columns={recentLoginsColumns}
            paginate={false}
            exportable={false}
            emptyMessage="No sign-in recorded."
          />
        </div>
      </div>

      <div>
        <h2 className="type-title-4 mb-3">Recent page views</h2>
        <DataTable
          records={pageviewRecords}
          columns={pageviewColumns}
          defaultPageSize={10}
          exportFileName="page-views"
          emptyMessage="No page view recorded."
        />
      </div>
    </div>
  );
}
