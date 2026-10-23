'use client';

import { useEffect, useState } from 'react';
import { Archive, ChevronLeft, ChevronRight, Forward, Inbox, CalendarRange } from 'lucide-react';
import { cn } from '@/lib/utils';
import { addDays, addWeeks, formatWeekRange, iterationName, type BoardIteration } from '@/lib/board';

export function IterationBar({
  backlog,
  week,
  today,
  iteration,
  showArchived,
  canCarryOver,
  onNavigateWeek,
  onToggleBacklog,
  onToggleArchived,
  onSaveGoal,
  onCarryOver,
}: {
  backlog: boolean;
  /** Monday of the shown week (ignored in backlog). */
  week: string;
  today: string;
  iteration: BoardIteration | null;
  showArchived: boolean;
  canCarryOver: boolean;
  onNavigateWeek: (week: string) => void;
  onToggleBacklog: () => void;
  onToggleArchived: () => void;
  onSaveGoal: (goal: string) => void;
  onCarryOver: () => void;
}) {
  const [goal, setGoal] = useState(iteration?.goal ?? '');
  useEffect(() => setGoal(iteration?.goal ?? ''), [iteration?.id, iteration?.goal]);

  const sunday = addDays(week, 6);

  return (
    <div className="board-iteration-bar">
      {backlog ? (
        <div className="board-iteration-heading">
          <h2 className="board-iteration-title">Backlog</h2>
          <span className="board-iteration-range">Tasks not scheduled in an iteration</span>
        </div>
      ) : (
        <>
          <div className="board-iteration-nav">
            <button
              type="button"
              className="board-icon-button"
              title="Previous iteration"
              onClick={() => onNavigateWeek(addWeeks(week, -1))}
            >
              <ChevronLeft size={14} />
            </button>
            <button
              type="button"
              className="board-icon-button"
              title="Next iteration"
              onClick={() => onNavigateWeek(addWeeks(week, 1))}
            >
              <ChevronRight size={14} />
            </button>
          </div>
          <div className="board-iteration-heading">
            <h2 className="board-iteration-title">{iterationName(week, today)}</h2>
            <span className="board-iteration-range">
              {formatWeekRange(iteration?.start_date ?? week, iteration?.end_date ?? sunday)}
              {iteration ? ` · ${iteration.iso_week}` : ''}
            </span>
          </div>
          {iteration && (
            <label className="board-iteration-goal">
              <span className="board-iteration-goal-label">Goal</span>
              <input
                className="board-iteration-goal-input"
                value={goal}
                maxLength={200}
                placeholder="One line on what this iteration delivers"
                onChange={(e) => setGoal(e.target.value)}
                onBlur={() => goal.trim() !== iteration.goal && onSaveGoal(goal.trim())}
                onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
              />
            </label>
          )}
        </>
      )}

      <div className="board-iteration-actions">
        {!backlog && iteration && (
          <button
            type="button"
            className="board-button"
            disabled={!canCarryOver}
            title="Move every task that is not Done to next week's iteration"
            onClick={onCarryOver}
          >
            <Forward size={13} /> Move unfinished to next
          </button>
        )}
        <button
          type="button"
          className={cn('board-button', showArchived && 'board-button-active')}
          aria-pressed={showArchived}
          onClick={onToggleArchived}
        >
          <Archive size={13} /> {showArchived ? 'Hide archived' : 'Show archived'}
        </button>
        <button type="button" className="board-button" onClick={onToggleBacklog}>
          {backlog ? (
            <>
              <CalendarRange size={13} /> Current iteration
            </>
          ) : (
            <>
              <Inbox size={13} /> Backlog
            </>
          )}
        </button>
      </div>
    </div>
  );
}
