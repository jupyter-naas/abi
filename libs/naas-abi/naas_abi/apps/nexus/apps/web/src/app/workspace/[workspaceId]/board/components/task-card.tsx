'use client';

import { CalendarDays, MessageSquareText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PropertyTags } from '@/components/database-view/primitives';
import { PRIORITY_LABELS, type BoardTask } from '@/lib/board';
import type { TaskPropertyKey, TaskSchema } from '../lib/task-schema';

function initials(name: string): string {
  const parts = name.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '?';
}

export function Avatars({ names }: { names: string[] }) {
  if (names.length === 0) return null;
  return (
    <span className="board-avatars" title={names.join(', ')}>
      {names.slice(0, 4).map((name, index) => (
        <span key={`${name}-${index}`} className="board-avatar">
          {initials(name)}
        </span>
      ))}
      {names.length > 4 && <span className="board-avatar">+{names.length - 4}</span>}
    </span>
  );
}

export function isOverdue(task: BoardTask, today: string): boolean {
  return !!task.due_date && task.stage !== 'done' && task.due_date < today;
}

/** One property of a task, as list, table and card cells show it. */
export function TaskPropertyValue({
  task,
  propertyKey,
  schema,
  today,
  className,
}: {
  task: BoardTask;
  propertyKey: TaskPropertyKey;
  schema: TaskSchema;
  today: string;
  className?: string;
}) {
  const values = schema.propertyValues(task, propertyKey);
  if (propertyKey === 'priority' && task.priority) {
    return (
      <span className={cn('board-tag', `board-priority-${task.priority}`, className)}>
        {PRIORITY_LABELS[task.priority]}
      </span>
    );
  }
  if (propertyKey === 'assignees' && values.length > 0) {
    return <Avatars names={values} />;
  }
  if (propertyKey === 'due_date' && values.length > 0) {
    return (
      <span className={cn('board-task-card-meta', isOverdue(task, today) && 'board-task-card-overdue', className)}>
        <CalendarDays size={11} className="mr-1 inline" />
        {values[0]}
      </span>
    );
  }
  return (
    <PropertyTags
      values={values}
      type={schema.propertyByKey[propertyKey].type}
      className={className}
    />
  );
}

export function TaskCard({
  task,
  visible,
  schema,
  today,
  onOpen,
}: {
  task: BoardTask;
  visible: TaskPropertyKey[];
  schema: TaskSchema;
  today: string;
  onOpen: () => void;
}) {
  // Empty properties stay off the card: a card shows what is set.
  const shown = visible.filter((key) => key !== 'content' && schema.propertyValues(task, key).length > 0);
  const preview = visible.includes('content') ? task.content.trim() : '';

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => e.key === 'Enter' && onOpen()}
      className={cn('board-task-card', task.archived && 'board-task-card-archived')}
    >
      <p className="board-task-card-title">{task.title}</p>
      {preview && (
        <p className="board-task-card-meta line-clamp-2">
          <MessageSquareText size={11} className="mr-1 inline" />
          {preview}
        </p>
      )}
      {shown.length > 0 && (
        <div className="board-task-card-props">
          {shown.map((key) => (
            <TaskPropertyValue key={key} task={task} propertyKey={key} schema={schema} today={today} />
          ))}
        </div>
      )}
    </div>
  );
}
