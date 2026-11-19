'use client';

import { Avatar } from '../avatar';
import { Card } from '../card';
import { formatRelative } from '../format';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import type { AnalyticsTabProps } from '../tabs';
import type { UsersResponse } from '../types';

export function UsersTab({ scope, filters, onUserPick }: AnalyticsTabProps) {
  const { data, loading, error } = useAnalytics<UsersResponse>(scope, '/users', filters);
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  if (!data) return null;
  if (data.users.length === 0)
    return (
      <Card title="No users">
        <EmptyBlock>No member activity in this period.</EmptyBlock>
      </Card>
    );
  return (
    <Card title="Users" subtitle="Click a row to see that user's activity">
      <div className="-mx-5 -my-5 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-5 py-3 font-medium">User</th>
              <th className="px-5 py-3 text-right font-medium">Sessions</th>
              <th className="px-5 py-3 text-right font-medium">Page views</th>
              <th className="px-5 py-3 text-right font-medium">Workspaces</th>
              <th className="px-5 py-3 text-right font-medium">Events</th>
              <th className="px-5 py-3 text-right font-medium">Last seen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {data.users.map((u) => (
              <tr
                key={u.user_id}
                className="cursor-pointer transition-colors hover:bg-muted/40"
                onClick={() => onUserPick(u.user_id)}
              >
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2.5">
                    <Avatar email={u.user_email} size={26} />
                    <span className="font-medium text-foreground">{u.user_email}</span>
                  </div>
                </td>
                <td className="px-5 py-3 text-right tabular-nums">{u.sessions}</td>
                <td className="px-5 py-3 text-right tabular-nums">{u.page_views}</td>
                <td className="px-5 py-3 text-right tabular-nums">{u.workspaces}</td>
                <td className="px-5 py-3 text-right tabular-nums">{u.total_events}</td>
                <td className="px-5 py-3 text-right text-muted-foreground">{formatRelative(u.last_seen)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
