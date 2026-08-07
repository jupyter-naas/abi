'use client';

import { useState, type ReactNode } from 'react';
import { ChevronRight, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { AppIcon, PropertyValue } from './primitives';
import {
  PROPERTY_BY_KEY, propertyText,
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
// Group wrapper
// ---------------------------------------------------------------------------

function GroupSection({
  group,
  collapsed,
  onToggle,
  children,
}: {
  group: RecordGroup;
  collapsed: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  // Ungrouped views render their rows straight through, no header.
  if (group.key === '__all__') return <>{children}</>;

  return (
    <section className="space-y-2">
      <button
        onClick={onToggle}
        className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight size={12} className={cn('transition-transform', !collapsed && 'rotate-90')} />
        <span>{group.label}</span>
        <span className="text-xs text-muted-foreground/70">{group.records.length}</span>
      </button>
      {!collapsed && children}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Layouts
// ---------------------------------------------------------------------------

function GalleryRows({ records, view, onOpen }: { records: AppRecord[] } & Omit<ViewProps, 'groups'>) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {records.map((record) => (
        <AppCard
          key={record.id}
          record={record}
          visible={view.visible}
          onOpen={() => onOpen(record)}
        />
      ))}
    </div>
  );
}

function ListRows({ records, view, onOpen }: { records: AppRecord[] } & Omit<ViewProps, 'groups'>) {
  return (
    <div className="divide-y divide-border/50 border border-border/50">
      {records.map((record) => (
        <div
          key={record.id}
          role="button"
          tabIndex={0}
          onClick={() => onOpen(record)}
          onKeyDown={(e) => e.key === 'Enter' && onOpen(record)}
          className="flex cursor-pointer items-center gap-3 px-3 py-2 transition-colors hover:bg-muted/40 focus:outline-none focus-visible:bg-muted/40"
        >
          <AppIcon record={record} size="sm" />
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{record.name}</span>
          {view.visible.map((key) => (
            <PropertyValue
              key={key}
              record={record}
              propertyKey={key}
              className="hidden max-w-[16rem] truncate md:block"
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function TableRows({ records, view, onOpen }: { records: AppRecord[] } & Omit<ViewProps, 'groups'>) {
  return (
    <div className="overflow-x-auto border border-border/50">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border/50 bg-muted/30 text-left">
            <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Name
            </th>
            {view.visible.map((key) => (
              <th
                key={key}
                className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              >
                {PROPERTY_BY_KEY[key].label}
              </th>
            ))}
            <th className="w-10 px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr
              key={record.id}
              tabIndex={0}
              onClick={() => onOpen(record)}
              onKeyDown={(e) => e.key === 'Enter' && onOpen(record)}
              className="cursor-pointer border-b border-border/30 transition-colors last:border-0 hover:bg-muted/40 focus:bg-muted/40 focus:outline-none"
            >
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <AppIcon record={record} size="sm" />
                  <span className="truncate font-medium">{record.name}</span>
                </div>
              </td>
              {view.visible.map((key) => (
                <td key={key} className="max-w-[22rem] px-3 py-2">
                  <div className="truncate" title={propertyText(record, key)}>
                    <PropertyValue record={record} propertyKey={key} />
                  </div>
                </td>
              ))}
              <td className="px-3 py-2 text-right">
                <ExternalLink size={12} className="inline text-muted-foreground" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BoardView({ view, groups, onOpen }: ViewProps) {
  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {groups.map((group) => (
        <div key={group.key} className="flex w-72 flex-shrink-0 flex-col gap-2">
          <div className="flex items-center gap-2 px-1">
            <span className="truncate text-sm font-medium">{group.label || 'All'}</span>
            <span className="text-xs text-muted-foreground">{group.records.length}</span>
          </div>
          <div className="flex flex-col gap-2">
            {group.records.map((record) => (
              <AppCard
                key={record.id}
                record={record}
                visible={view.visible}
                onOpen={() => onOpen(record)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Body
// ---------------------------------------------------------------------------

export function DatabaseBody({ view, groups, onOpen }: ViewProps) {
  const [collapsedGroups, setCollapsedGroups] = useState<string[]>([]);

  if (view.type === 'board') {
    return <BoardView view={view} groups={groups} onOpen={onOpen} />;
  }

  const toggleGroup = (key: string) =>
    setCollapsedGroups((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );

  return (
    <div className="space-y-5">
      {groups.map((group) => {
        const groupKey = `${view.id}:${group.key}`;
        const rows =
          view.type === 'table' ? (
            <TableRows records={group.records} view={view} onOpen={onOpen} />
          ) : view.type === 'list' ? (
            <ListRows records={group.records} view={view} onOpen={onOpen} />
          ) : (
            <GalleryRows records={group.records} view={view} onOpen={onOpen} />
          );
        return (
          <GroupSection
            key={group.key}
            group={group}
            collapsed={collapsedGroups.includes(groupKey)}
            onToggle={() => toggleGroup(groupKey)}
          >
            {rows}
          </GroupSection>
        );
      })}
    </div>
  );
}
