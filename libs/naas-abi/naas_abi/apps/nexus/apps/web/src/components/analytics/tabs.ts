/**
 * Nexus Analytics: the tabs a scope shows, and what every tab receives. Pure, so the
 * rule (no Workspaces tab in a workspace; only Overview, Events and Chats for one user)
 * is tested without a page.
 */
import { scopeHasWorkspaces, type AnalyticsFilters, type AnalyticsScope } from './scope';
import type { AnalyticsGranularity } from './types';

export type AnalyticsTab = 'overview' | 'users' | 'sessions' | 'pages' | 'workspaces' | 'chats' | 'events';

export const ANALYTICS_TABS: { key: AnalyticsTab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'users', label: 'Users' },
  { key: 'sessions', label: 'Sessions' },
  { key: 'pages', label: 'Pages' },
  { key: 'workspaces', label: 'Workspaces' },
  { key: 'chats', label: 'Chats' },
  { key: 'events', label: 'Events' },
];

/** What a single user's view keeps: their detail (Overview), their events and their chats. */
const USER_TABS: ReadonlySet<AnalyticsTab> = new Set(['overview', 'events', 'chats']);

/** The tabs of a scope: Workspaces only in an organization; three tabs once a user is picked. */
export function analyticsTabs(
  scope: AnalyticsScope,
  { userSelected = false }: { userSelected?: boolean } = {}
): { key: AnalyticsTab; label: string }[] {
  return ANALYTICS_TABS.filter(
    (tab) => (tab.key !== 'workspaces' || scopeHasWorkspaces(scope)) && (!userSelected || USER_TABS.has(tab.key))
  );
}

/** The tab to show: `tab` when the scope offers it, Overview otherwise. */
export function shownTab(tab: AnalyticsTab, tabs: { key: AnalyticsTab }[]): AnalyticsTab {
  return tabs.some((t) => t.key === tab) ? tab : 'overview';
}

/** What every tab is given by the section. */
export interface AnalyticsTabProps {
  scope: AnalyticsScope;
  filters: AnalyticsFilters;
  /** The organization's IANA timezone: every time shown is in it. */
  timeZone: string;
  /** Bucket size of the period's time series. */
  granularity: AnalyticsGranularity;
  /** Picks an in-scope member by `user_id` (the user filter). */
  onUserPick: (userId: string) => void;
}
