import { describe, expect, it } from 'vitest';
import {
  ALL,
  ANALYTICS_PERIODS,
  DEFAULT_PERIOD,
  analyticsBasePath,
  analyticsQuery,
  analyticsScopeKey,
  analyticsUrl,
  initialAnalyticsFilters,
  isAnalyticsPeriod,
  periodGranularity,
  scopeHasWorkspaces,
  type AnalyticsFilters,
  type AnalyticsScope,
} from './scope';

const org: AnalyticsScope = { kind: 'organization', orgId: 'org-1' };
const ws: AnalyticsScope = { kind: 'workspace', workspaceId: 'ws-1' };
const filters = (over: Partial<AnalyticsFilters> = {}): AnalyticsFilters => ({ ...initialAnalyticsFilters(), ...over });

describe('analytics scope → URL', () => {
  it('reads an organization under /api/organizations/{id}/analytics and a workspace under /api/workspaces/{id}/analytics', () => {
    expect(analyticsBasePath(org)).toBe('/api/organizations/org-1/analytics');
    expect(analyticsBasePath(ws)).toBe('/api/workspaces/ws-1/analytics');
    expect(analyticsUrl(org, '/overview', filters())).toBe('/api/organizations/org-1/analytics/overview?period=today');
    expect(analyticsUrl(ws, 'overview', filters())).toBe('/api/workspaces/ws-1/analytics/overview?period=today');
  });

  it('asks /access without a query', () => {
    expect(analyticsUrl(org, '/access')).toBe('/api/organizations/org-1/analytics/access');
    expect(analyticsUrl(ws, '/access')).toBe('/api/workspaces/ws-1/analytics/access');
  });

  it('encodes the ids in the path', () => {
    expect(analyticsBasePath({ kind: 'organization', orgId: 'a/b c' })).toBe('/api/organizations/a%2Fb%20c/analytics');
    expect(analyticsBasePath({ kind: 'workspace', workspaceId: '../x' })).toBe('/api/workspaces/..%2Fx/analytics');
  });

  it('sends the period, then the workspace (organization only) and the user filters', () => {
    const picked = filters({ period: 'this_week', workspaceId: 'ws-9', userId: 'u-1' });
    expect(analyticsQuery(org, picked)).toBe('period=this_week&workspace_id=ws-9&user_id=u-1');
    // A workspace takes no workspace filter: it is the path.
    expect(analyticsQuery(ws, picked)).toBe('period=this_week&user_id=u-1');
  });

  it('sends no filter for "all"', () => {
    expect(analyticsQuery(org, filters({ period: 'this_month', workspaceId: ALL, userId: ALL }))).toBe('period=this_month');
  });

  it('adds the extra parameters of a read (events limit)', () => {
    expect(analyticsUrl(ws, '/events', filters({ period: 'yesterday' }), { limit: '200' })).toBe(
      '/api/workspaces/ws-1/analytics/events?period=yesterday&limit=200'
    );
  });

  it('keys a scope, and gives only an organization several workspaces', () => {
    expect(analyticsScopeKey(org)).toBe('organization:org-1');
    expect(analyticsScopeKey(ws)).toBe('workspace:ws-1');
    expect(scopeHasWorkspaces(org)).toBe(true);
    expect(scopeHasWorkspaces(ws)).toBe(false);
  });
});

describe('analytics periods', () => {
  it('offers the four calendar periods, Today first and by default', () => {
    expect(ANALYTICS_PERIODS.map((p) => p.label)).toEqual(['Today', 'Yesterday', 'This week', 'This month']);
    expect(ANALYTICS_PERIODS.map((p) => p.id)).toEqual(['today', 'yesterday', 'this_week', 'this_month']);
    expect(DEFAULT_PERIOD).toBe('today');
    expect(initialAnalyticsFilters()).toEqual({ period: 'today', userId: ALL, workspaceId: ALL });
  });

  it('accepts no other period (rolling windows are gone)', () => {
    for (const id of ['today', 'yesterday', 'this_week', 'this_month']) expect(isAnalyticsPeriod(id)).toBe(true);
    for (const id of ['last_7_days', 'last_30_days', 'last_90_days', '', null]) expect(isAnalyticsPeriod(id)).toBe(false);
  });

  it('reads Today and Yesterday by the hour, This week and This month by the day', () => {
    expect(periodGranularity('today')).toBe('hour');
    expect(periodGranularity('yesterday')).toBe('hour');
    expect(periodGranularity('this_week')).toBe('day');
    expect(periodGranularity('this_month')).toBe('day');
  });
});
