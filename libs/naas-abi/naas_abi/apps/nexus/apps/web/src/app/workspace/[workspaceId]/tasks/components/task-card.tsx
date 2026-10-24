'use client';

import { CalendarDays, Github, MessageSquareText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PropertyTags } from '@/components/database-view/primitives';
import { DONE_STAGE, choiceColor, choiceLabel, type TaskChoice, type Task } from '@/lib/tasks';
import type { TaskPropertyKey, TaskSchema } from '../lib/task-schema';

function initials(name: string): string {
  const parts = name.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '?';
}

export function Avatars({ names }: { names: string[] }) {
  if (names.length === 0) return null;
  return (
    <span className="tasks-avatars" title={names.join(', ')}>
      {names.slice(0, 4).map((name, index) => (
        <span key={`${name}-${index}`} className="tasks-avatar">
          {initials(name)}
        </span>
      ))}
      {names.length > 4 && <span className="tasks-avatar">+{names.length - 4}</span>}
    </span>
  );
}

export function isOverdue(task: Task, today: string): boolean {
  return !!task.due_date && task.stage !== DONE_STAGE && task.due_date < today;
}

/** One property of a task, as list, table and card cells show it. */
export function TaskPropertyValue({
  task,
  propertyKey,
  schema,
  priorities,
  today,
  className,
}: {
  task: Task;
  propertyKey: TaskPropertyKey;
  schema: TaskSchema;
  priorities: TaskChoice[];
  today: string;
  className?: string;
}) {
  const values = schema.propertyValues(task, propertyKey);
  if (propertyKey === 'priority' && task.priority) {
    return (
      <span className={cn('tasks-tag', `tasks-color-${choiceColor(priorities, task.priority)}`, className)}>
        {choiceLabel(priorities, task.priority)}
      </span>
    );
  }
  if (propertyKey === 'assignees' && values.length > 0) {
    return <Avatars names={values} />;
  }
  if (propertyKey === 'github_issue' && values.length > 0) {
    return (
      <a
        href={task.github_issue_url}
        target="_blank"
        rel="noreferrer"
        title={task.github_issue_url}
        className={cn('tasks-task-card-meta tasks-github-link', className)}
        // Opens the issue, not the task.
        onClick={(e) => e.stopPropagation()}
      >
        <Github size={11} className="mr-1 inline" />
        {values[0]}
      </a>
    );
  }
  if (propertyKey === 'due_date' && values.length > 0) {
    return (
      <span className={cn('tasks-task-card-meta', isOverdue(task, today) && 'tasks-task-card-overdue', className)}>
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
  priorities,
  today,
  onOpen,
}: {
  task: Task;
  visible: TaskPropertyKey[];
  schema: TaskSchema;
  priorities: TaskChoice[];
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
      className={cn('tasks-task-card', task.archived && 'tasks-task-card-archived')}
    >
      <p className="tasks-task-card-title">{task.title}</p>
      {preview && (
        <p className="tasks-task-card-meta line-clamp-2">
          <MessageSquareText size={11} className="mr-1 inline" />
          {preview}
        </p>
      )}
      {shown.length > 0 && (
        <div className="tasks-task-card-props">
          {shown.map((key) => (
            <TaskPropertyValue
              key={key}
              task={task}
              propertyKey={key}
              schema={schema}
              priorities={priorities}
              today={today}
            />
          ))}
        </div>
      )}
    </div>
  );
}
