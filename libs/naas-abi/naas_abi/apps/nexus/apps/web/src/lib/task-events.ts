/**
 * One-line summaries of task events, shared by the sidebar feed and the task
 * drawer's Activity tab. The feed names the task ("moved “Spec” from Ready to
 * Review"); the drawer, already on the task, leaves it out ("moved it from …").
 */

import { githubIssueRef, parseIsoDate, type TaskActivity, type TaskActivityField } from '@/lib/tasks';

export interface TaskEventNames {
  member: (userId: string) => string;
  /** Iteration name; null is the backlog. */
  iteration: (iterationId: string | null) => string;
  stage: (key: string) => string;
  priority: (key: string) => string;
}

/** What each event kind is called in the feed settings. */
export const TASK_EVENT_LABELS: Record<TaskActivityField, string> = {
  created: 'Task created',
  title: 'Renamed',
  content: 'Description edited',
  stage: 'Stage changed',
  assignees: 'Assignees changed',
  priority: 'Priority changed',
  due_date: 'Due date changed',
  labels: 'Labels changed',
  github_issue: 'GitHub issue linked or unlinked',
  iteration: 'Moved to another iteration',
  archived: 'Archived or restored',
  deleted: 'Task deleted',
  comment_added: 'Comment added',
  comment_replied: 'Reply to a comment',
  comment_removed: 'Comment removed',
};

/** Event kinds grouped as the settings show them. */
export const TASK_EVENT_GROUPS: { label: string; fields: TaskActivityField[] }[] = [
  { label: 'Tasks', fields: ['created', 'archived', 'deleted'] },
  {
    label: 'Changes',
    fields: ['title', 'content', 'stage', 'assignees', 'priority', 'due_date', 'labels', 'github_issue', 'iteration'],
  },
  { label: 'Comments', fields: ['comment_added', 'comment_replied', 'comment_removed'] },
];

const asList = (value: unknown): string[] => (Array.isArray(value) ? value.map(String) : []);
const asText = (value: unknown): string => (value === null || value === undefined ? '' : String(value));

const joinNames = (names: string[]) =>
  names.length <= 2 ? names.join(' and ') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;

const day = (value: unknown) =>
  parseIsoDate(String(value)).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });

/**
 * What happened, after the actor's name: "moved “Spec” from Ready to Review".
 * ``withTask`` names the task (the feed); without it the task is "it".
 */
export function describeTaskEvent(
  entry: TaskActivity,
  names: TaskEventNames,
  { withTask = false }: { withTask?: boolean } = {},
): string {
  const task = withTask ? `“${entry.task_title || 'Untitled task'}”` : 'it';
  const on = withTask ? ` on ${task}` : '';
  const quote = (value: unknown) => (asText(value) ? `: “${asText(value)}”` : '');

  switch (entry.field) {
    case 'created':
      return withTask ? `created ${task}` : 'created the task';
    case 'title':
      return `renamed “${asText(entry.old_value)}” to “${asText(entry.new_value)}”`;
    case 'content':
      return withTask ? `edited the description of ${task}` : 'edited the description';
    case 'stage':
      return `moved ${task} from ${names.stage(asText(entry.old_value))} to ${names.stage(asText(entry.new_value))}`;
    case 'assignees': {
      const before = asList(entry.old_value);
      const after = asList(entry.new_value);
      const added = after.filter((id) => !before.includes(id)).map(names.member);
      const removed = before.filter((id) => !after.includes(id)).map(names.member);
      const target = withTask ? task : 'the task';
      const parts = [
        added.length ? `assigned ${joinNames(added)} to ${target}` : '',
        removed.length ? `unassigned ${joinNames(removed)} from ${target}` : '',
      ].filter(Boolean);
      return parts.join(' and ') || `changed the assignees${on}`;
    }
    case 'priority':
      return entry.new_value
        ? `set the priority${on} to ${names.priority(asText(entry.new_value))}`
        : `removed the priority${on}`;
    case 'due_date':
      return entry.new_value ? `set the due date${on} to ${day(entry.new_value)}` : `cleared the due date${on}`;
    case 'labels': {
      const before = asList(entry.old_value);
      const after = asList(entry.new_value);
      const added = after.filter((l) => !before.includes(l));
      const removed = before.filter((l) => !after.includes(l));
      const parts = [
        added.length ? `added ${added.length === 1 ? 'label' : 'labels'} ${joinNames(added)}` : '',
        removed.length ? `removed ${removed.length === 1 ? 'label' : 'labels'} ${joinNames(removed)}` : '',
      ].filter(Boolean);
      return `${parts.join(' and ') || 'changed the labels'}${on}`;
    }
    case 'github_issue': {
      const issue = (value: unknown) => githubIssueRef(asText(value)) ?? asText(value);
      return entry.new_value
        ? `linked ${withTask ? task : 'it'} to GitHub issue ${issue(entry.new_value)}`
        : `unlinked GitHub issue ${issue(entry.old_value)}${withTask ? ` from ${task}` : ''}`;
    }
    case 'iteration': {
      const target = entry.new_value ? names.iteration(asText(entry.new_value)) : 'the backlog';
      return `moved ${task} to ${target}`;
    }
    case 'archived':
      return entry.new_value ? `archived ${withTask ? task : 'the task'}` : `restored ${withTask ? task : 'the task'}`;
    case 'deleted':
      return withTask ? `deleted ${task}` : 'deleted the task';
    case 'comment_added':
      return `commented${on}${quote(entry.new_value)}`;
    case 'comment_replied': {
      const to = entry.old_value ? ` to ${names.member(asText(entry.old_value))}` : '';
      return `replied${to}${on}${quote(entry.new_value)}`;
    }
    case 'comment_removed': {
      const whose = entry.new_value && entry.new_value === entry.actor_id
        ? 'their comment'
        : entry.new_value
          ? `${names.member(asText(entry.new_value))}’s comment`
          : 'a comment';
      return `removed ${whose}${on}`;
    }
    default:
      return `changed ${entry.field}${on}`;
  }
}
