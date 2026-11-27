'use client';

import { useCallback, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAnalyticsAccess } from '@/hooks/use-analytics-access';
import { UserFilter, WorkspaceFilter } from './filters';
import { PeriodControl } from './period-control';
import {
  ALL,
  DEFAULT_PERIOD,
  initialAnalyticsFilters,
  keepUserInWorkspace,
  periodGranularity,
  scopeHasWorkspaces,
  type AnalyticsFilters,
  type AnalyticsScope,
} from './scope';
import { ErrorBlock, LoadingBlock } from './states';
import { analyticsTabs, shownTab, type AnalyticsTab, type AnalyticsTabProps } from './tabs';
import { EventsTab } from './tabs/events-tab';
import { OverviewTab } from './tabs/overview-tab';
import { PagesTab } from './tabs/pages-tab';
import { SessionsTab } from './tabs/sessions-tab';
import { UsersTab } from './tabs/users-tab';
import { WorkspacesTab } from './tabs/workspaces-tab';
import { useAnalytics } from './use-analytics';
import type { UsersResponse, WorkspacesResponse } from './types';
import { EmptyState } from '@/components/ui/empty-state';

// Chats (the conversations table, a conversation, its export) and one user's detail load on
// first open (#1609). The other tabs are under 1 kB each once compressed: a chunk of their
// own would cost a request on open and more than it saves.
const loading = () => <LoadingBlock />;
const ChatsTab = dynamic(() => import('./tabs/chats-tab').then((m) => m.ChatsTab), { loading });
const UserDetailTab = dynamic(() => import('./tabs/user-detail').then((m) => m.UserDetailTab), { loading });

/** The directories (members, workspaces) do not depend on the period: read once per scope. */
const DIRECTORY_FILTERS: AnalyticsFilters = { period: DEFAULT_PERIOD, userId: ALL, workspaceId: ALL };

/**
 * Nexus Analytics of one scope, as a settings section: an organization (its members across
 * its workspaces) or a workspace (its members, in it). The API resolves the scope; this
 * shows what it answers, for the period and filters picked here. Rendered inside the
 * organization's or the workspace's settings layout, it wears their theme (tokens only).
 */
export function AnalyticsSection({ scope }: { scope: AnalyticsScope }) {
  const { status: accessStatus, access } = useAnalyticsAccess(scope, { refresh: true });
  const canRead = access?.can_read === true;
  // The charts start with the access read. A refusal replaces them once that read answers.
  const refused = accessStatus !== 'checking' && !canRead;
  const timeZone = access?.timezone || 'UTC';

  const [filters, setFilters] = useState<AnalyticsFilters>(initialAnalyticsFilters);
  const [tab, setTab] = useState<AnalyticsTab>('overview');
  const hasWorkspaces = scopeHasWorkspaces(scope);

  const users = useAnalytics<UsersResponse>(scope, '/users', DIRECTORY_FILTERS, { skip: refused });
  const workspaces = useAnalytics<WorkspacesResponse>(scope, '/workspaces', DIRECTORY_FILTERS, {
    skip: refused || !hasWorkspaces,
  });
  const directory = useMemo(() => users.data?.directory ?? [], [users.data]);
  // In an organization, a picked workspace narrows the user list to its members.
  const userOptions = useMemo(
    () =>
      hasWorkspaces && filters.workspaceId !== ALL
        ? directory.filter((u) => u.workspace_ids.includes(filters.workspaceId))
        : directory,
    [directory, hasWorkspaces, filters.workspaceId]
  );

  const userSelected = filters.userId !== ALL;
  const tabs = analyticsTabs(scope, { userSelected });
  const activeTab = shownTab(tab, tabs);

  const onUserPick = useCallback((userId: string) => {
    setFilters((f) => ({ ...f, userId }));
    setTab('overview');
  }, []);

  if (accessStatus === 'error' && !access) return <ErrorBlock message="The analytics access could not be read." />;
  if (refused) {
    return (
      <EmptyState framed
        icon={<BarChart3 size={40} className="opacity-40" />}
        title="You cannot read these analytics"
        description={`Your role and policies do not let you read this ${
          scope.kind === 'organization' ? "organization's" : "workspace's"
        } analytics. Its owners and admins can.`}
      />
    );
  }

  const tabProps: AnalyticsTabProps = {
    scope,
    filters,
    timeZone,
    granularity: periodGranularity(filters.period),
    onUserPick,
  };

  return (
    <div className="space-y-6 text-foreground">
      <div className="flex flex-wrap items-center gap-3">
        {hasWorkspaces && (
          <WorkspaceFilter
            value={filters.workspaceId}
            onChange={(workspaceId) => setFilters((f) => keepUserInWorkspace(f, workspaceId, directory))}
            workspaces={workspaces.data?.directory ?? []}
          />
        )}
        <UserFilter
          value={filters.userId}
          onChange={(userId) => setFilters((f) => ({ ...f, userId }))}
          users={userOptions}
        />
        <PeriodControl
          value={filters.period}
          onChange={(period) => setFilters((f) => ({ ...f, period }))}
          timeZone={timeZone}
        />
      </div>

      <nav aria-label="Analytics views" className="flex flex-wrap items-center gap-1 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            aria-current={activeTab === t.key ? 'page' : undefined}
            onClick={() => setTab(t.key)}
            className={cn(
              '-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors',
              activeTab === t.key
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {activeTab === 'overview' &&
        (userSelected ? (
          <UserDetailTab {...tabProps} onClear={() => setFilters((f) => ({ ...f, userId: ALL }))} />
        ) : (
          <OverviewTab {...tabProps} />
        ))}
      {activeTab === 'users' && <UsersTab {...tabProps} />}
      {activeTab === 'sessions' && <SessionsTab {...tabProps} />}
      {activeTab === 'pages' && <PagesTab {...tabProps} />}
      {activeTab === 'workspaces' && <WorkspacesTab {...tabProps} />}
      {activeTab === 'chats' && (
        <ChatsTab {...tabProps} canReadMessages={access?.can_read_conversations === true} directory={directory} />
      )}
      {activeTab === 'events' && <EventsTab {...tabProps} />}
    </div>
  );
}
