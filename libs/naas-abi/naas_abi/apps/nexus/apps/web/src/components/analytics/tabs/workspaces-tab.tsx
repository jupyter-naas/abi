'use client';

import { Layers } from 'lucide-react';
import { Card } from '../card';
import { formatNumber } from '../format';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import type { AnalyticsTabProps } from '../tabs';
import type { WorkspacesResponse } from '../types';

/** Organization scope only: activity per workspace of the organization. */
export function WorkspacesTab({ scope, filters }: AnalyticsTabProps) {
  const { data, loading, error } = useAnalytics<WorkspacesResponse>(scope, '/workspaces', filters, {
    skip: scope.kind !== 'organization',
  });
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  const ws = data?.workspaces ?? [];
  return (
    <Card title="Workspaces" subtitle="Activity per workspace in this period">
      {ws.length === 0 ? (
        <EmptyBlock>No workspace activity.</EmptyBlock>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
          {ws.map((w) => (
            <div key={w.workspace_id} className="border border-border/60 bg-background p-4">
              <div className="flex items-center gap-2">
                <Layers size={14} className="text-primary" />
                <h4 className="truncate font-medium text-foreground">{w.workspace_name}</h4>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                {[
                  { label: 'Users', value: w.active_users },
                  { label: 'Sessions', value: w.sessions },
                  { label: 'Events', value: w.events },
                ].map((m) => (
                  <div key={m.label}>
                    <p className="text-xl font-semibold tabular-nums text-foreground">{formatNumber(m.value)}</p>
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{m.label}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
