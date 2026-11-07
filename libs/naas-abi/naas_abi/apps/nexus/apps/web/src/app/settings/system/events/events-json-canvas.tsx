'use client';

import { MonacoEditor } from '@/components/monaco/monaco-editor';
import type { PlatformEvent } from './bfo-event-projection';

export function prettyEventJson(event: PlatformEvent): string {
  return JSON.stringify(event, null, 2);
}

export function EventsJsonCanvas({ event }: { event: PlatformEvent | null }) {
  if (!event) {
    return (
      <div
        className="flex min-h-0 flex-1 items-center justify-center bg-background text-sm text-muted-foreground"
        data-testid="admin-events-json-empty"
      >
        Select an event
      </div>
    );
  }

  return (
    <div className="relative min-h-0 flex-1" data-testid="admin-events-json">
      <div className="absolute inset-0 min-h-0">
        <MonacoEditor
          language="json"
          value={prettyEventJson(event)}
          path={`event-${encodeURIComponent(event._uri)}.json`}
          options={{ readOnly: true }}
        />
      </div>
    </div>
  );
}
