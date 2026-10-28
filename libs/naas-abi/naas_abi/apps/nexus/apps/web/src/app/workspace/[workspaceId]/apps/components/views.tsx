'use client';

import { ExternalLink } from 'lucide-react';
import { DatabaseBody as SharedDatabaseBody } from '@/components/database-view/views';
import { AppIcon, PropertyValue } from './primitives';
import {
  APPS_SCHEMA, PROPERTY_BY_KEY,
  type AppRecord, type PropertyKey, type RecordGroup, type ViewConfig,
} from './types';

interface ViewProps {
  view: ViewConfig;
  groups: RecordGroup[];
  onOpen: (record: AppRecord) => void;
}

// ---------------------------------------------------------------------------
// Card — shared by gallery and board
// ---------------------------------------------------------------------------

function AppCard({
  record,
  visible,
  onOpen,
}: {
  record: AppRecord;
  visible: PropertyKey[];
  onOpen: () => void;
}) {
  const showsDescription = visible.includes('description');
  const rest = visible.filter((key) => key !== 'description');

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => e.key === 'Enter' && onOpen()}
      className="glass-card flex cursor-pointer flex-col gap-3 p-4 transition-all hover:-translate-y-0.5 hover:border-workspace-accent/40 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-workspace-accent/40"
    >
      <div className="flex items-start gap-3">
        <AppIcon record={record} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold leading-tight">{record.name}</h3>
          {showsDescription && record.description && (
            <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
              {record.description}
            </p>
          )}
        </div>
      </div>

      {rest.length > 0 && (
        <div className="space-y-1.5 border-t border-border/50 pt-2.5">
          {rest.map((key) => (
            <div key={key} className="flex items-baseline gap-2">
              <span className="w-20 flex-shrink-0 truncate text-[11px] uppercase tracking-wide text-muted-foreground">
                {PROPERTY_BY_KEY[key].label}
              </span>
              <PropertyValue record={record} propertyKey={key} className="min-w-0 flex-1 truncate" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Body
// ---------------------------------------------------------------------------

export function DatabaseBody({ view, groups, onOpen }: ViewProps) {
  return (
    <SharedDatabaseBody
      schema={APPS_SCHEMA}
      view={view}
      groups={groups}
      getId={(record) => record.id}
      onOpen={onOpen}
      renderCard={(record, visible) => (
        <AppCard record={record} visible={visible} onOpen={() => onOpen(record)} />
      )}
      renderValue={(record, key) => <PropertyValue record={record} propertyKey={key} />}
      renderLeading={(record) => <AppIcon record={record} size="sm" />}
      renderTableTrailing={() => <ExternalLink size={12} className="inline text-muted-foreground" />}
    />
  );
}
