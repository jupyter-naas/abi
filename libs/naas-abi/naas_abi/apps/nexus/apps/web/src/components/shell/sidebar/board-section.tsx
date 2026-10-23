'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useSearchParams } from 'next/navigation';
import { CalendarRange, Inbox, SquareKanban } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  boardApi,
  boardPath,
  formatWeekRange,
  toIsoDate,
  weekStart,
  type BoardIteration,
} from '@/lib/board';
import { CollapsibleSection } from './collapsible-section';
import { getWorkspacePath } from './utils';

const rowClass = (active: boolean) =>
  cn(
    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
    active ? 'bg-muted font-medium text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
  );

/** Board panel: this week, the backlog, then every iteration, newest first. */
export function BoardSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [iterations, setIterations] = useState<BoardIteration[]>([]);

  const onBoard = pathname?.includes('/board') ?? false;
  const backlog = onBoard && searchParams?.get('backlog') === '1';
  const currentWeek = weekStart(toIsoDate(new Date()));
  const shownWeek = onBoard && !backlog ? weekStart(searchParams?.get('week') || currentWeek) : null;

  // Refresh when the board route changes, so iterations created there show up.
  const routeKey = `${pathname}?${searchParams?.toString() ?? ''}`;
  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    boardApi
      .listIterations(workspaceId)
      .then((rows) => !cancelled && setIterations([...rows].reverse()))
      .catch(() => !cancelled && setIterations([]));
    return () => {
      cancelled = true;
    };
  }, [workspaceId, routeKey]);

  if (!workspaceId) return null;

  return (
    <CollapsibleSection
      id="board"
      icon={<SquareKanban size={18} />}
      label="Board"
      description="Project tasks in weekly iterations"
      href={getWorkspacePath(workspaceId, '/board')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <Link href={boardPath(workspaceId)} className={rowClass(shownWeek === currentWeek)}>
        <CalendarRange size={14} />
        <span>Current iteration</span>
      </Link>
      <Link href={boardPath(workspaceId, { backlog: true })} className={rowClass(backlog)}>
        <Inbox size={14} />
        <span>Backlog</span>
      </Link>
      {iterations.length > 0 && (
        <p className="px-2 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          Iterations
        </p>
      )}
      {iterations.map((iteration) => (
        <Link
          key={iteration.id}
          href={boardPath(workspaceId, { week: iteration.start_date })}
          className={rowClass(shownWeek === iteration.start_date)}
          title={iteration.goal || undefined}
        >
          <span className="min-w-0 flex-1">
            <span className="block truncate">{formatWeekRange(iteration.start_date, iteration.end_date)}</span>
            {iteration.goal && <span className="block truncate text-xs text-muted-foreground">{iteration.goal}</span>}
          </span>
        </Link>
      ))}
    </CollapsibleSection>
  );
}
