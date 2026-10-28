'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { isRecordDrag, readDraggedRecordId, startRowDrag } from './drag';

/**
 * Month calendar layout: rows placed on the day their date property falls on,
 * weeks starting on Monday. Rows without a date are listed under the grid.
 */

const pad = (n: number) => String(n).padStart(2, '0');
const isoDay = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** The 42 days (6 weeks, Monday first) shown for the month of ``month``. */
export function monthGrid(month: Date): string[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(first);
  start.setDate(1 - ((first.getDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, i) => {
    const day = new Date(start);
    day.setDate(start.getDate() + i);
    return isoDay(day);
  });
}

export function CalendarView<R>({
  records,
  getId,
  getDate,
  dateLabel,
  renderItem,
  onOpen,
  draggable,
  onMoveToDate,
}: {
  records: R[];
  getId: (record: R) => string;
  /** YYYY-MM-DD the row sits on, or null. */
  getDate: (record: R) => string | null;
  /** Name of the date property ("Due date"), for the undated list. */
  dateLabel: string;
  renderItem: (record: R) => ReactNode;
  onOpen: (record: R) => void;
  draggable?: boolean;
  /** Dropping a row on a day; omit to make days inert. */
  onMoveToDate?: (record: R, day: string) => void;
}) {
  const today = isoDay(new Date());
  const [month, setMonth] = useState(() => new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [dropDay, setDropDay] = useState<string | null>(null);

  const days = useMemo(() => monthGrid(month), [month]);
  const byDay = useMemo(() => {
    const map = new Map<string, R[]>();
    for (const record of records) {
      const day = getDate(record);
      if (!day) continue;
      map.set(day, [...(map.get(day) ?? []), record]);
    }
    return map;
  }, [records, getDate]);
  const undated = records.filter((r) => !getDate(r));
  const byId = new Map(records.map((r) => [getId(r), r]));
  const monthPrefix = `${month.getFullYear()}-${pad(month.getMonth() + 1)}`;

  const shift = (delta: number) => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1));

  const item = (record: R) => (
    <div
      key={getId(record)}
      role="button"
      tabIndex={0}
      draggable={draggable}
      onDragStart={draggable ? (e) => startRowDrag(e, getId(record)) : undefined}
      onClick={() => onOpen(record)}
      onKeyDown={(e) => e.key === 'Enter' && onOpen(record)}
      className="flex min-w-0 cursor-pointer items-center gap-1.5 border border-border/60 bg-card px-1.5 py-0.5 text-xs hover:border-workspace-accent/50"
    >
      {renderItem(record)}
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">
          {month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <button type="button" onClick={() => shift(-1)} title="Previous month" className="flex h-7 w-7 items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground">
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            onClick={() => setMonth(new Date(new Date().getFullYear(), new Date().getMonth(), 1))}
            className="h-7 px-2 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            Today
          </button>
          <button type="button" onClick={() => shift(1)} title="Next month" className="flex h-7 w-7 items-center justify-center text-muted-foreground hover:bg-muted hover:text-foreground">
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 border-l border-t border-border/50">
        {WEEKDAYS.map((name) => (
          <div key={name} className="border-b border-r border-border/50 px-1.5 py-1 text-[11px] font-medium text-muted-foreground">
            {name}
          </div>
        ))}
        {days.map((day) => {
          const rows = byDay.get(day) ?? [];
          return (
            <div
              key={day}
              onDragOver={(e) => {
                if (!onMoveToDate || !isRecordDrag(e)) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (dropDay !== day) setDropDay(day);
              }}
              onDragLeave={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDropDay(null);
              }}
              onDrop={(e) => {
                setDropDay(null);
                const record = byId.get(readDraggedRecordId(e) ?? '');
                if (!record || !onMoveToDate) return;
                e.preventDefault();
                if (getDate(record) !== day) onMoveToDate(record, day);
              }}
              className={cn(
                'flex min-h-[6rem] min-w-0 flex-col gap-1 border-b border-r border-border/50 p-1',
                !day.startsWith(monthPrefix) && 'bg-muted/30',
                dropDay === day && 'bg-workspace-accent/5 ring-1 ring-inset ring-workspace-accent/30',
              )}
            >
              <span
                className={cn(
                  'self-end px-1 text-[11px]',
                  day === today ? 'bg-workspace-accent font-semibold text-white' : 'text-muted-foreground',
                )}
              >
                {Number(day.slice(8))}
              </span>
              {rows.map(item)}
            </div>
          );
        })}
      </div>

      {undated.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">
            No {dateLabel.toLowerCase()} ({undated.length})
          </p>
          <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-4">{undated.map(item)}</div>
        </div>
      )}
    </div>
  );
}
