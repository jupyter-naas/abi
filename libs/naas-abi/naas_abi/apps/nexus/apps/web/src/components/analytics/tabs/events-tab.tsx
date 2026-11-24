'use client';

import { Card } from '../card';
import { EventIcon, formatEventName } from '../event-icon';
import { formatDateTime } from '../format';
import { EmptyBlock, ErrorBlock, LoadingBlock } from '../states';
import { useAnalytics } from '../use-analytics';
import type { AnalyticsTabProps } from '../tabs';
import type { EventsResponse } from '../types';

/** The API caps `limit` at 500; 200 is its default. */
export const EVENTS_LIMIT = '200';

export function EventsTab({ scope, filters, timeZone }: AnalyticsTabProps) {
  const { data, loading, error } = useAnalytics<EventsResponse>(scope, '/events', filters, {
    extra: { limit: EVENTS_LIMIT },
  });
  if (loading && !data) return <LoadingBlock />;
  if (error) return <ErrorBlock message={error} />;
  const events = data?.events ?? [];
  return (
    <Card title="Event stream" subtitle="Most recent events matching the filters">
      {events.length === 0 ? (
        <EmptyBlock>No events in this period.</EmptyBlock>
      ) : (
        <ul className="-mx-5 -my-5 divide-y divide-border/50">
          {events.map((e) => (
            <li key={e.event_id} className="flex items-start gap-3 px-5 py-3 text-sm">
              <EventIcon name={e.event_name} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="font-medium text-foreground">{formatEventName(e.event_name)}</span>
                  {e.page_path && <span className="text-xs text-muted-foreground">{e.page_path}</span>}
                  {e.properties && Object.keys(e.properties).length > 0 && (
                    <span className="break-all font-mono text-xs text-muted-foreground">{JSON.stringify(e.properties)}</span>
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
              <div className="flex-shrink-0 whitespace-nowrap text-right text-xs text-muted-foreground">
                <div>{formatDateTime(e.timestamp, timeZone)}</div>
                <div className="font-mono opacity-70">{e.session_id.slice(0, 12)}</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
