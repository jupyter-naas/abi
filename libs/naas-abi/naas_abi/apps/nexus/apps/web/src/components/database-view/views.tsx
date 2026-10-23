'use client';

import { useState, type ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DatabaseSchema, RecordGroup, ViewConfig } from './model';
import { CalendarView } from './calendar';
import { isRecordDrag, readDraggedRecordId, startRowDrag } from './drag';

export type ViewLayout = 'gallery' | 'table' | 'list' | 'board' | 'calendar';

export interface DatabaseBodyProps<R, K extends string, T extends ViewLayout> {
  schema: DatabaseSchema<R, K>;
  view: ViewConfig<K, T>;
  groups: RecordGroup<R>[];
  getId: (record: R) => string;
  onOpen: (record: R) => void;
  /** Card used by gallery and board layouts. */
  renderCard: (record: R, visible: K[]) => ReactNode;
  /** One property value of a row (list and table cells). */
  renderValue: (record: R, key: K, className?: string) => ReactNode;
  /** Icon or marker before the title in list and table rows. */
  renderLeading?: (record: R) => ReactNode;
  /** Last table cell (e.g. an "open" hint). */
  renderTableTrailing?: (record: R) => ReactNode;
  /** Board only: called when a card is dropped on another column. */
  onMoveToGroup?: (record: R, groupKey: string) => void;
  /** Rows and cards can be dragged out, e.g. onto tabs (see `readDraggedRecordId`). */
  draggableRows?: boolean;
  /** Board only: framed columns sharing the available width (stacked on narrow screens). */
  fitColumns?: boolean;
  /** Calendar only: the day a row sits on, and what dropping it on a day does. */
  calendar?: {
    getDate: (record: R) => string | null;
    dateLabel: string;
    onMoveToDate?: (record: R, day: string) => void;
  };
  /** Board only: extra content under a column's cards (e.g. "New task"). */
  renderColumnFooter?: (group: RecordGroup<R>) => ReactNode;
  /** Board only: a marker next to the column title (e.g. a stage dot). */
  renderColumnMarker?: (group: RecordGroup<R>) => ReactNode;
}

// ---------------------------------------------------------------------------
// Group wrapper
// ---------------------------------------------------------------------------

function GroupSection<R>({
  group,
  collapsed,
  onToggle,
  children,
}: {
  group: RecordGroup<R>;
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

type RowsProps<R, K extends string, T extends ViewLayout> = Omit<DatabaseBodyProps<R, K, T>, 'groups'> & {
  records: R[];
};

function GalleryRows<R, K extends string, T extends ViewLayout>({
  records, view, getId, renderCard, draggableRows,
}: RowsProps<R, K, T>) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
      {records.map((record) => (
        <div
          key={getId(record)}
          draggable={draggableRows}
          onDragStart={draggableRows ? (e) => startRowDrag(e, getId(record)) : undefined}
        >
          {renderCard(record, view.visible)}
        </div>
      ))}
    </div>
  );
}

function ListRows<R, K extends string, T extends ViewLayout>({
  records, view, schema, getId, onOpen, renderValue, renderLeading, draggableRows,
}: RowsProps<R, K, T>) {
  return (
    <div className="divide-y divide-border/50 border border-border/50">
      {records.map((record) => (
        <div
          key={getId(record)}
          role="button"
          tabIndex={0}
          draggable={draggableRows}
          onDragStart={draggableRows ? (e) => startRowDrag(e, getId(record)) : undefined}
          onClick={() => onOpen(record)}
          onKeyDown={(e) => e.key === 'Enter' && onOpen(record)}
          className="flex cursor-pointer items-center gap-3 px-3 py-2 transition-colors hover:bg-muted/40 focus:outline-none focus-visible:bg-muted/40"
        >
          {renderLeading?.(record)}
          <span className="min-w-0 flex-1 truncate text-sm font-medium">
            {schema.propertyText(record, schema.titleKey)}
          </span>
          {view.visible.map((key) => (
            <span key={key} className="hidden max-w-[16rem] truncate md:block">
              {renderValue(record, key)}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

function TableRows<R, K extends string, T extends ViewLayout>({
  records, view, schema, getId, onOpen, renderValue, renderLeading, renderTableTrailing, draggableRows,
}: RowsProps<R, K, T>) {
  return (
    <div className="overflow-x-auto border border-border/50">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border/50 bg-muted/30 text-left">
            <th className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {schema.propertyByKey[schema.titleKey].label}
            </th>
            {view.visible.map((key) => (
              <th
                key={key}
                className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              >
                {schema.propertyByKey[key].label}
              </th>
            ))}
            {renderTableTrailing && <th className="w-10 px-3 py-2" />}
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr
              key={getId(record)}
              tabIndex={0}
              draggable={draggableRows}
              onDragStart={draggableRows ? (e) => startRowDrag(e, getId(record)) : undefined}
              onClick={() => onOpen(record)}
              onKeyDown={(e) => e.key === 'Enter' && onOpen(record)}
              className="cursor-pointer border-b border-border/30 transition-colors last:border-0 hover:bg-muted/40 focus:bg-muted/40 focus:outline-none"
            >
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  {renderLeading?.(record)}
                  <span className="truncate font-medium">{schema.propertyText(record, schema.titleKey)}</span>
                </div>
              </td>
              {view.visible.map((key) => (
                <td key={key} className="max-w-[22rem] px-3 py-2">
                  <div className="truncate" title={schema.propertyText(record, key)}>
                    {renderValue(record, key)}
                  </div>
                </td>
              ))}
              {renderTableTrailing && (
                <td className="px-3 py-2 text-right">{renderTableTrailing(record)}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


function BoardView<R, K extends string, T extends ViewLayout>({
  view, groups, getId, renderCard, onMoveToGroup, renderColumnFooter, renderColumnMarker,
  draggableRows, fitColumns,
}: DatabaseBodyProps<R, K, T>) {
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const byId = new Map(groups.flatMap((g) => g.records.map((r) => [getId(r), r] as const)));
  const droppable = !!onMoveToGroup;
  const draggable = droppable || !!draggableRows;

  return (
    <div
      className={cn(
        'pb-2',
        fitColumns
          ? 'grid grid-cols-1 gap-3 md:auto-cols-[minmax(0,1fr)] md:grid-flow-col'
          : 'flex gap-4 overflow-x-auto',
      )}
    >
      {groups.map((group) => (
        <div
          key={group.key}
          onDragOver={(e) => {
            if (!droppable || !isRecordDrag(e)) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            if (dropTarget !== group.key) setDropTarget(group.key);
          }}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDropTarget(null);
          }}
          onDrop={(e) => {
            setDropTarget(null);
            const id = readDraggedRecordId(e) ?? '';
            const record = byId.get(id);
            if (!record || !onMoveToGroup) return;
            e.preventDefault();
            if (!group.records.some((r) => getId(r) === id)) onMoveToGroup(record, group.key);
          }}
          className={cn(
            'flex flex-col gap-2 transition-colors',
            // Fitted columns are framed so each stage reads as its own lane.
            fitColumns ? 'min-w-0 border border-border bg-muted/20 p-2' : 'w-72 flex-shrink-0 p-1',
            dropTarget === group.key && 'border-workspace-accent/50 bg-workspace-accent/5 ring-1 ring-workspace-accent/30',
          )}
        >
          <div className="flex items-center gap-2 px-1">
            {renderColumnMarker?.(group)}
            <span className="truncate text-sm font-medium">{group.label || 'All'}</span>
            <span className="text-xs text-muted-foreground">{group.records.length}</span>
          </div>
          <div className="flex min-h-[3rem] flex-col gap-2">
            {group.records.map((record) => (
              <div
                key={getId(record)}
                draggable={draggable}
                onDragStart={(e) => {
                  startRowDrag(e, getId(record));
                  setDragging(getId(record));
                }}
                onDragEnd={() => setDragging(null)}
                className={cn(draggable && 'cursor-grab active:cursor-grabbing', dragging === getId(record) && 'opacity-40')}
              >
                {renderCard(record, view.visible)}
              </div>
            ))}
          </div>
          {renderColumnFooter?.(group)}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Body
// ---------------------------------------------------------------------------

export function DatabaseBody<R, K extends string, T extends ViewLayout>(props: DatabaseBodyProps<R, K, T>) {
  const { view, groups } = props;
  const [collapsedGroups, setCollapsedGroups] = useState<string[]>([]);

  if (view.type === 'board') {
    return <BoardView {...props} />;
  }
  if (view.type === 'calendar' && props.calendar) {
    const { schema, getId, onOpen, renderLeading, draggableRows, calendar } = props;
    return (
      <CalendarView
        records={groups.flatMap((g) => g.records).filter((r, i, all) => all.indexOf(r) === i)}
        getId={getId}
        getDate={calendar.getDate}
        dateLabel={calendar.dateLabel}
        onOpen={onOpen}
        draggable={draggableRows || !!calendar.onMoveToDate}
        onMoveToDate={calendar.onMoveToDate}
        renderItem={(record) => (
          <>
            {renderLeading?.(record)}
            <span className="truncate">{schema.propertyText(record, schema.titleKey)}</span>
          </>
        )}
      />
    );
  }

  const toggleGroup = (key: string) =>
    setCollapsedGroups((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );

  return (
    <div className="space-y-5">
      {/* Empty groups only make sense as board columns (a drop target). */}
      {groups.filter((group) => group.records.length > 0).map((group) => {
        const groupKey = `${view.id}:${group.key}`;
        const rowsProps = { ...props, records: group.records };
        const rows =
          view.type === 'table' ? (
            <TableRows {...rowsProps} />
          ) : view.type === 'list' ? (
            <ListRows {...rowsProps} />
          ) : (
            <GalleryRows {...rowsProps} />
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
