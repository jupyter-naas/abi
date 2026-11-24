'use client';

import { Avatar } from '../avatar';
import { Card } from '../card';
import { formatDateTime, formatDuration } from '../format';
import { scopeHasWorkspaces } from '../scope';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import type { AnalyticsTabProps } from '../tabs';
import type { SessionsResponse } from '../types';

const SHOWN = 200;

export function SessionsTab({ scope, filters, timeZone }: AnalyticsTabProps) {
  const { data, loading, error } = useAnalytics<SessionsResponse>(scope, '/sessions', filters);
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  const sessions = data?.sessions ?? [];
  const workspaces = scopeHasWorkspaces(scope);
  return (
    <Card title="Sessions" subtitle={`${sessions.length.toLocaleString()} session(s) in this period`}>
      <div className="-mx-5 -my-5 overflow-x-auto">
        {sessions.length === 0 ? (
          <EmptyBlock>No sessions match these filters.</EmptyBlock>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-5 py-3 font-medium">User</th>
                {workspaces && <th className="px-5 py-3 font-medium">Workspace</th>}
                <th className="px-5 py-3 font-medium">Started</th>
                <th className="px-5 py-3 text-right font-medium">Duration</th>
                <th className="px-5 py-3 text-right font-medium">Page views</th>
                <th className="px-5 py-3 text-right font-medium">Events</th>
                <th className="px-5 py-3 font-medium">Device</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {sessions.slice(0, SHOWN).map((s) => (
                <tr key={s.session_id} className="transition-colors hover:bg-muted/40">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <Avatar email={s.user_email} size={22} />
                      <span className="truncate text-foreground">{s.user_email}</span>
                    </div>
                  </td>
                  {workspaces && <td className="px-5 py-3 text-muted-foreground">{s.workspace_name ?? '—'}</td>}
                  <td className="px-5 py-3 text-muted-foreground">{formatDateTime(s.started_at, timeZone)}</td>
                  <td className="px-5 py-3 text-right tabular-nums">{formatDuration(s.duration_seconds)}</td>
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
        {sessions.length > SHOWN && (
          <div className="border-t border-border/50 px-5 py-3 text-xs text-muted-foreground">
            Showing the first {SHOWN} of {sessions.length.toLocaleString()} sessions.
          </div>
        )}
      </div>
    </Card>
  );
}
