/**
 * Workspace tasks as a Notion-style database (`components/database-view`).
 *
 * Properties read display values (stage labels, member names, formatted
 * dates), so filters, search and grouping work on what the user sees. Stages
 * and priorities carry their configured order: board columns follow the stage
 * order and include empty stages; sorting by priority goes most urgent first.
 */

import {
  createSchema,
  type DatabaseSchema,
  type PropertyDef,
  type ViewConfig,
} from '@/components/database-view/model';
import type { DatabaseViewsOptions } from '@/components/database-view/use-database-views';
import { choiceLabel, parseIsoDate, type TasksSettings, type Task } from '@/lib/tasks';

export type TaskPropertyKey =
  | 'title'
  | 'stage'
  | 'assignees'
  | 'priority'
  | 'project'
  | 'labels'
  | 'due_date'
  | 'iteration'
  | 'content'
  | 'created_by'
  | 'created_at'
  | 'updated_by'
  | 'updated_at';

export type TaskViewType = 'board' | 'table' | 'gallery' | 'calendar';
export type TaskViewConfig = ViewConfig<TaskPropertyKey, TaskViewType>;
export type TaskSchema = DatabaseSchema<Task, TaskPropertyKey>;

export interface TaskSchemaContext {
  /** Display name of a user id; unknown ids still render. */
  memberName: (userId: string) => string;
  /** Display name of an iteration id ("Oct 19 – Oct 25"). */
  iterationLabel: (iterationId: string) => string;
  /** Stages and priorities, in their configured order. */
  settings: Pick<TasksSettings, 'stages' | 'priorities'>;
}

const one = (value: string | null | undefined): string[] => (value ? [value] : []);

export function formatDate(value: string | null): string {
  if (!value) return '';
  // Dates (YYYY-MM-DD) are calendar days; timestamps are UTC instants.
  const date = value.length === 10 ? parseIsoDate(value) : new Date(value.endsWith('Z') ? value : `${value}Z`);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function createTaskSchema(ctx: TaskSchemaContext): TaskSchema {
  const properties: PropertyDef<Task, TaskPropertyKey>[] = [
    { key: 'title', label: 'Title', type: 'title', values: (t) => one(t.title) },
    {
      key: 'stage',
      label: 'Stage',
      type: 'select',
      values: (t) => one(choiceLabel(ctx.settings.stages, t.stage)),
      options: ctx.settings.stages.map((s) => s.label),
    },
    {
      key: 'assignees',
      label: 'Assignees',
      type: 'person',
      values: (t) => t.assignee_ids.map(ctx.memberName),
    },
    {
      key: 'priority',
      label: 'Priority',
      type: 'select',
      values: (t) => one(choiceLabel(ctx.settings.priorities, t.priority)),
      options: ctx.settings.priorities.map((p) => p.label),
    },
    { key: 'project', label: 'Project', type: 'select', values: (t) => one(t.project) },
    { key: 'labels', label: 'Labels', type: 'multi', values: (t) => t.labels.filter(Boolean) },
    {
      key: 'due_date',
      label: 'Due date',
      type: 'date',
      values: (t) => one(formatDate(t.due_date)),
      sortValue: (t) => t.due_date ?? '',
    },
    {
      key: 'iteration',
      label: 'Iteration',
      type: 'select',
      values: (t) => one(t.iteration_id ? ctx.iterationLabel(t.iteration_id) : ''),
    },
    { key: 'content', label: 'Content', type: 'text', values: (t) => one(t.content.trim()) },
    { key: 'created_by', label: 'Created by', type: 'person', values: (t) => one(t.created_by && ctx.memberName(t.created_by)) },
    {
      key: 'created_at',
      label: 'Created',
      type: 'date',
      values: (t) => one(formatDate(t.created_at)),
      sortValue: (t) => t.created_at ?? '',
    },
    { key: 'updated_by', label: 'Last updated by', type: 'person', values: (t) => one(t.updated_by && ctx.memberName(t.updated_by)) },
    {
      key: 'updated_at',
      label: 'Last updated',
      type: 'date',
      values: (t) => one(formatDate(t.updated_at)),
      sortValue: (t) => t.updated_at ?? '',
    },
  ];
  return createSchema(properties);
}

export const TASK_PROPERTY_KEYS: TaskPropertyKey[] = [
  'title', 'stage', 'assignees', 'priority', 'project', 'labels', 'due_date', 'iteration',
  'content', 'created_by', 'created_at', 'updated_by', 'updated_at',
];

export const TASK_VIEW_TYPE_LABELS: Record<TaskViewType, string> = {
  board: 'Board',
  table: 'Table',
  gallery: 'Gallery',
  calendar: 'Calendar',
};

const DEFAULT_VISIBLE: Record<TaskViewType, TaskPropertyKey[]> = {
  board: ['assignees', 'priority', 'labels', 'due_date'],
  table: ['stage', 'assignees', 'priority', 'project', 'labels', 'due_date', 'updated_at'],
  gallery: ['stage', 'assignees', 'priority', 'labels', 'due_date'],
  calendar: [],
};

function createTaskView(type: TaskViewType, name: string): Omit<TaskViewConfig, 'id'> {
  return {
    name,
    type,
    visible: [...DEFAULT_VISIBLE[type]],
    filters: [],
    sort: type === 'board' ? { property: 'priority', direction: 'asc' } : null,
    groupBy: type === 'board' ? 'stage' : null,
  };
}

/** One saved view (properties, filters, sort, grouping) per user and workspace. */
function taskViews(
  storagePrefix: string,
  initial: Omit<TaskViewConfig, 'id'>,
): DatabaseViewsOptions<TaskPropertyKey, TaskViewType> {
  return {
    storagePrefix,
    viewTypeLabels: TASK_VIEW_TYPE_LABELS,
    propertyKeys: TASK_PROPERTY_KEYS,
    titleKey: 'title',
    createView: createTaskView,
    defaultViews: () => [{ ...initial, visible: [...initial.visible] }],
  };
}

/** The current, last and next iterations: stage columns, most urgent first. */
export const ITERATION_VIEWS = taskViews('nexus.tasks.iteration-view', createTaskView('board', 'Current iteration'));

/** Inbox: one group per day the requests came in, newest day and request first. */
export const INBOX_VIEWS = taskViews('nexus.tasks.inbox-view.v2', {
  ...createTaskView('table', 'Inbox'),
  visible: ['assignees', 'priority', 'project', 'labels', 'created_by', 'created_at'],
  sort: { property: 'created_at', direction: 'desc' },
  groupBy: 'created_at',
});

/** Backlog: one group per priority, Urgent to Low, newest first within each. */
export const BACKLOG_VIEWS = taskViews('nexus.tasks.backlog-view.v2', {
  ...createTaskView('table', 'Backlog'),
  visible: ['stage', 'assignees', 'priority', 'project', 'labels', 'due_date'],
  sort: { property: 'created_at', direction: 'desc' },
  groupBy: 'priority',
});
