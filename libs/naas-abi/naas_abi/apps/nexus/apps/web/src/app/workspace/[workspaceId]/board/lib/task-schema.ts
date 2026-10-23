/**
 * Board tasks as a Notion-style database (`components/database-view`).
 *
 * Properties read display values (stage labels, member names, formatted
 * dates), so filters, search and grouping work on what the user sees. Stages
 * and priorities carry their natural order: board columns follow the stage
 * order and include empty stages; sorting by priority goes Urgent → Low.
 */

import {
  createSchema,
  type DatabaseSchema,
  type PropertyDef,
  type ViewConfig,
} from '@/components/database-view/model';
import type { DatabaseViewsOptions } from '@/components/database-view/use-database-views';
import {
  BOARD_PRIORITIES,
  BOARD_STAGES,
  PRIORITY_LABELS,
  STAGE_LABELS,
  parseIsoDate,
  type BoardTask,
} from '@/lib/board';

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

export type TaskViewType = 'board' | 'table' | 'list';
export type TaskViewConfig = ViewConfig<TaskPropertyKey, TaskViewType>;
export type TaskSchema = DatabaseSchema<BoardTask, TaskPropertyKey>;

export interface TaskSchemaContext {
  /** Display name of a user id; unknown ids still render. */
  memberName: (userId: string) => string;
  /** Display name of an iteration id ("Oct 19 – Oct 25"). */
  iterationLabel: (iterationId: string) => string;
}

const one = (value: string | null | undefined): string[] => (value ? [value] : []);

export function formatDate(value: string | null): string {
  if (!value) return '';
  // Dates (YYYY-MM-DD) are calendar days; timestamps are UTC instants.
  const date = value.length === 10 ? parseIsoDate(value) : new Date(value.endsWith('Z') ? value : `${value}Z`);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function createTaskSchema(ctx: TaskSchemaContext): TaskSchema {
  const properties: PropertyDef<BoardTask, TaskPropertyKey>[] = [
    { key: 'title', label: 'Title', type: 'title', values: (t) => one(t.title) },
    {
      key: 'stage',
      label: 'Stage',
      type: 'select',
      values: (t) => one(STAGE_LABELS[t.stage]),
      options: BOARD_STAGES.map((s) => STAGE_LABELS[s]),
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
      values: (t) => one(t.priority ? PRIORITY_LABELS[t.priority] : ''),
      options: BOARD_PRIORITIES.map((p) => PRIORITY_LABELS[p]),
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
  list: 'List',
};

const DEFAULT_VISIBLE: Record<TaskViewType, TaskPropertyKey[]> = {
  board: ['assignees', 'priority', 'labels', 'due_date'],
  table: ['stage', 'assignees', 'priority', 'project', 'labels', 'due_date', 'updated_at'],
  list: ['stage', 'assignees', 'priority'],
};

/** Saved views of the board, per user and workspace. */
export const TASK_VIEWS: DatabaseViewsOptions<TaskPropertyKey, TaskViewType> = {
  storagePrefix: 'nexus.board.views',
  viewTypeLabels: TASK_VIEW_TYPE_LABELS,
  propertyKeys: TASK_PROPERTY_KEYS,
  titleKey: 'title',
  createView: (type, name) => ({
    name,
    type,
    visible: [...DEFAULT_VISIBLE[type]],
    filters: [],
    sort: type === 'board' ? { property: 'priority', direction: 'asc' } : null,
    groupBy: type === 'board' ? 'stage' : null,
  }),
  defaultViews: () => [
    TASK_VIEWS.createView('board', 'Board'),
    TASK_VIEWS.createView('table', 'Table'),
  ],
};
