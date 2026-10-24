/**
 * Workspace tasks: weekly iterations, tasks, comments and activity.
 *
 * API: /api/tasks (see services/tasks in the API). An iteration is a run of
 * whole weeks (length and start weekday come from the workspace's tasks
 * settings), keyed by its first day; iterations never overlap. The page asks
 * for "the iteration of this date" with the user's local date, so boundaries
 * follow the user's timezone. Stages, priorities and suggested labels also
 * come from the settings.
 *
 * The page shows five scopes: the current, last and next iterations (their
 * tasks past Inbox), Inbox (every task waiting for triage, scheduled or not)
 * and Backlog (triaged tasks without an iteration).
 */
import { authFetch } from '@/stores/auth';

/** A stage key from the settings; ``inbox`` and ``done`` always exist. */
export type TaskStage = string;
/** A priority key from the settings. */
export type TaskPriority = string;

export const INBOX_STAGE = 'inbox';
export const DONE_STAGE = 'done';

/** Colors a stage or priority may use; each maps to theme-aware classes. */
export const TASK_PALETTE = [
  'slate', 'blue', 'amber', 'purple', 'cyan', 'green', 'red', 'orange', 'yellow', 'pink',
] as const;
export type TaskColor = (typeof TASK_PALETTE)[number];

/** A stage or a priority. ``key`` is empty for one not saved yet. */
export type TaskChoice = { key: string; label: string; color: TaskColor };

export const WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

/** What a task event records, in the order the settings list them (matches the API). */
export const TASK_ACTIVITY_FIELDS = [
  'created',
  'title',
  'content',
  'stage',
  'assignees',
  'priority',
  'due_date',
  'labels',
  'github_issue',
  'iteration',
  'archived',
  'deleted',
  'comment_added',
  'comment_replied',
  'comment_removed',
] as const;

export type TaskActivityField = (typeof TASK_ACTIVITY_FIELDS)[number];

const GITHUB_ISSUE_RE = /^https:\/\/github\.com\/([A-Za-z0-9-]+)\/([A-Za-z0-9._-]+)\/issues\/(\d+)\/?(?:[?#].*)?$/;

/** "acme/abi#42" for a GitHub issue URL; null when it is not one (the API refuses those). */
export function githubIssueRef(url: string | null | undefined): string | null {
  const match = GITHUB_ISSUE_RE.exec((url ?? '').trim());
  return match ? `${match[1]}/${match[2]}#${match[3]}` : null;
}

export const MIN_FEED_LIMIT = 5;
export const MAX_FEED_LIMIT = 100;

export type TasksSettings = {
  iteration_weeks: number;
  /** 0 = Monday … 6 = Sunday. */
  iteration_start_day: number;
  iteration_anchor: string;
  /** Ordered; Inbox first, Done last. */
  stages: TaskChoice[];
  /** Ordered, most urgent first. */
  priorities: TaskChoice[];
  /** Stage of a task created in an iteration. */
  default_stage: TaskStage;
  suggested_labels: string[];
  /** Sidebar activity feed: shown or not, which event kinds, how many events. */
  feed_enabled: boolean;
  feed_events: TaskActivityField[];
  feed_limit: number;
  updated_by: string | null;
  updated_at: string | null;
  /** Whether the caller may save changes (owners and admins). */
  can_edit: boolean;
};

/** What a workspace without saved settings uses (mirrors the API defaults). */
export const DEFAULT_TASKS_SETTINGS: TasksSettings = {
  iteration_weeks: 1,
  iteration_start_day: 0,
  iteration_anchor: '2024-01-01',
  stages: [
    { key: 'inbox', label: 'Inbox', color: 'slate' },
    { key: 'ready', label: 'Ready', color: 'blue' },
    { key: 'in_progress', label: 'In progress', color: 'amber' },
    { key: 'on_hold', label: 'On hold', color: 'purple' },
    { key: 'review', label: 'Review', color: 'cyan' },
    { key: 'done', label: 'Done', color: 'green' },
  ],
  priorities: [
    { key: 'urgent', label: 'Urgent', color: 'red' },
    { key: 'high', label: 'High', color: 'orange' },
    { key: 'medium', label: 'Medium', color: 'yellow' },
    { key: 'low', label: 'Low', color: 'slate' },
  ],
  default_stage: 'ready',
  suggested_labels: ['Feature', 'Bug', 'Data', 'Model', 'Research', 'Chore'],
  feed_enabled: true,
  feed_events: [...TASK_ACTIVITY_FIELDS],
  feed_limit: 20,
  updated_by: null,
  updated_at: null,
  can_edit: false,
};

/** Display label of a key; unknown keys (removed since) show as they are. */
export function choiceLabel(choices: TaskChoice[], key: string | null): string {
  if (!key) return '';
  return choices.find((c) => c.key === key)?.label ?? key;
}

export function choiceColor(choices: TaskChoice[], key: string | null): TaskColor {
  return choices.find((c) => c.key === key)?.color ?? 'slate';
}

/** The key behind a display label (board columns are grouped by label). */
export function choiceFromLabel(choices: TaskChoice[], label: string): string | null {
  return choices.find((c) => c.label === label)?.key ?? null;
}

export type TaskIteration = {
  id: string;
  workspace_id: string;
  /** YYYY-MM-DD, first day. */
  start_date: string;
  /** YYYY-MM-DD, last day (inclusive). */
  end_date: string;
  /** e.g. 2026-W43, or 2026-W43–W44 for two weeks */
  iso_week: string;
  goal: string;
  created_by: string | null;
  created_at: string | null;
  updated_by: string | null;
  updated_at: string | null;
};

export type Task = {
  id: string;
  workspace_id: string;
  title: string;
  content: string;
  stage: TaskStage;
  iteration_id: string | null;
  priority: TaskPriority | null;
  due_date: string | null;
  labels: string[];
  assignee_ids: string[];
  /** https://github.com/<owner>/<repo>/issues/<number>, or empty. */
  github_issue_url: string;
  archived: boolean;
  archived_at: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_by: string | null;
  updated_at: string | null;
};

export type TaskComment = {
  id: string;
  task_id: string;
  author_id: string | null;
  body: string;
  created_at: string;
  /** The comment this one replies to (threads are one level deep). */
  parent_id: string | null;
};

export type TaskActivity = {
  id: string;
  task_id: string;
  /** The task's title when it happened (the task may be deleted since). */
  task_title: string;
  actor_id: string | null;
  field: TaskActivityField | string;
  old_value: unknown;
  new_value: unknown;
  created_at: string | null;
};

export type TasksMember = {
  user_id: string;
  name: string | null;
  email: string | null;
  role: string;
};

export type TaskFields = Partial<
  Pick<
    Task,
    | 'title'
    | 'content'
    | 'stage'
    | 'iteration_id'
    | 'priority'
    | 'due_date'
    | 'labels'
    | 'assignee_ids'
    | 'github_issue_url'
  >
>;

// -- Weeks ----------------------------------------------------------------------

const pad = (n: number) => String(n).padStart(2, '0');

/** A local calendar date as YYYY-MM-DD (not UTC: the user's day). */
export function toIsoDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Parse YYYY-MM-DD as a local calendar date. */
export function parseIsoDate(value: string): Date {
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

/** Monday of the ISO week the date falls in, as YYYY-MM-DD. */
export function weekStart(value: string): string {
  const date = parseIsoDate(value);
  const offset = (date.getDay() + 6) % 7; // Monday = 0
  date.setDate(date.getDate() - offset);
  return toIsoDate(date);
}

export function addDays(value: string, days: number): string {
  const date = parseIsoDate(value);
  date.setDate(date.getDate() + days);
  return toIsoDate(date);
}

export function addWeeks(value: string, weeks: number): string {
  return addDays(value, weeks * 7);
}

/** "Oct 19 – Oct 25, 2026" (year once when both ends share it). */
export function formatWeekRange(start: string, end: string, locale?: string): string {
  const a = parseIsoDate(start);
  const b = parseIsoDate(end);
  const day = (d: Date) => d.toLocaleDateString(locale, { month: 'short', day: 'numeric' });
  if (a.getFullYear() === b.getFullYear()) return `${day(a)} – ${day(b)}, ${b.getFullYear()}`;
  const full = (d: Date) => d.toLocaleDateString(locale, { month: 'short', day: 'numeric', year: 'numeric' });
  return `${full(a)} – ${full(b)}`;
}

// -- Scopes ---------------------------------------------------------------------

export type TasksScope = 'current' | 'last' | 'next' | 'inbox' | 'backlog';

/** Tab order: triage first, then the iterations oldest to newest. Current stays the default tab. */
export const TASK_SCOPES: TasksScope[] = ['inbox', 'backlog', 'last', 'current', 'next'];

export const SCOPE_LABELS: Record<TasksScope, string> = {
  current: 'Current iteration',
  last: 'Last iteration',
  next: 'Next iteration',
  inbox: 'Inbox',
  backlog: 'Backlog',
};

export function parseScope(value: string | null | undefined): TasksScope {
  return TASK_SCOPES.find((scope) => scope === value) ?? 'current';
}

/** The iteration a date falls in, if one exists. */
export function iterationContaining(iterations: TaskIteration[], day: string): TaskIteration | null {
  return iterations.find((i) => i.start_date <= day && day <= i.end_date) ?? null;
}

/**
 * A day inside an iteration scope, given the current iteration: what to ask
 * the API for when the scope's iteration does not exist yet. Null for Inbox
 * and Backlog.
 */
export function scopeDay(scope: TasksScope, current: TaskIteration | null, today: string): string | null {
  if (scope === 'current') return today;
  if (!current) return null;
  if (scope === 'last') return addDays(current.start_date, -1);
  if (scope === 'next') return addDays(current.end_date, 1);
  return null;
}

/** The iteration each iteration scope shows, from today's iteration outwards. */
export function scopeIterations(
  iterations: TaskIteration[],
  today: string,
): Record<'current' | 'last' | 'next', TaskIteration | null> {
  const current = iterationContaining(iterations, today);
  const at = (scope: TasksScope) => {
    const day = scopeDay(scope, current, today);
    return day ? iterationContaining(iterations, day) : null;
  };
  return { current, last: at('last'), next: at('next') };
}

/**
 * Whether a task shows in a scope. ``iterationId`` is the scope's iteration
 * (null when it has none yet). Inbox tasks only show in Inbox.
 */
export function taskInScope(task: Task, scope: TasksScope, iterationId: string | null): boolean {
  if (scope === 'inbox') return task.stage === INBOX_STAGE;
  if (task.stage === INBOX_STAGE) return false;
  if (scope === 'backlog') return task.iteration_id === null;
  return iterationId !== null && task.iteration_id === iterationId;
}

/**
 * What dropping a task on a scope changes, or null when it is already there.
 * Leaving Inbox puts a task in ``defaultStage``; going to Inbox keeps its
 * iteration, so it returns there once triaged.
 */
export function fieldsForScope(
  task: Task,
  scope: TasksScope,
  iterationId: string | null,
  defaultStage: TaskStage = DEFAULT_TASKS_SETTINGS.default_stage,
): TaskFields | null {
  if (taskInScope(task, scope, iterationId)) return null;
  if (scope === 'inbox') return { stage: INBOX_STAGE };
  const stage = task.stage === INBOX_STAGE ? { stage: defaultStage } : {};
  return { ...stage, iteration_id: scope === 'backlog' ? null : iterationId };
}

/** The scope a task shows in, or null for an iteration outside last/current/next. */
export function scopeOfTask(
  task: Task,
  scopes: Record<'current' | 'last' | 'next', TaskIteration | null>,
): TasksScope | null {
  if (task.stage === INBOX_STAGE) return 'inbox';
  if (task.iteration_id === null) return 'backlog';
  return (['current', 'last', 'next'] as const).find((scope) => scopes[scope]?.id === task.iteration_id) ?? null;
}

/** Assignee filter value for tasks nobody is assigned to. */
export const UNASSIGNED = '__unassigned__';

/** ``assignees`` holds user ids and/or UNASSIGNED; empty means everyone. */
export function matchesAssignee(task: Task, assignees: string[]): boolean {
  if (assignees.length === 0) return true;
  if (task.assignee_ids.length === 0) return assignees.includes(UNASSIGNED);
  return task.assignee_ids.some((id) => assignees.includes(id));
}

/** Priority filter value for tasks without a priority. */
export const NO_PRIORITY = '__no_priority__';

/** ``priorities`` holds priority keys and/or NO_PRIORITY; empty means any. */
export function matchesPriority(task: Task, priorities: string[]): boolean {
  if (priorities.length === 0) return true;
  return priorities.includes(task.priority ?? NO_PRIORITY);
}

/** Label filter value for tasks without a label. */
export const NO_LABEL = '__no_label__';

/** ``labels`` holds label names and/or NO_LABEL; empty means any. */
export function matchesLabel(task: Task, labels: string[]): boolean {
  if (labels.length === 0) return true;
  if (task.labels.length === 0) return labels.includes(NO_LABEL);
  return task.labels.some((label) => labels.includes(label));
}

/** The sidebar filters, shared with the Tasks page. Empty lists filter nothing. */
export type TasksFilters = { assignees: string[]; priorities: string[]; labels: string[] };
export type TasksFilterKind = keyof TasksFilters;
export const NO_FILTERS: TasksFilters = { assignees: [], priorities: [], labels: [] };

/** Every active filter must match (AND); within one, any selected value does (OR). */
export function matchesFilters(task: Task, filters: TasksFilters): boolean {
  return (
    matchesAssignee(task, filters.assignees) &&
    matchesPriority(task, filters.priorities) &&
    matchesLabel(task, filters.labels)
  );
}

export function tasksSettingsPath(workspaceId: string): string {
  return `/workspace/${encodeURIComponent(workspaceId)}/tasks/settings`;
}

/** ``newTask`` opens the Tasks page's "New task" prompt on arrival. */
export function tasksPath(
  workspaceId: string,
  params?: { view?: TasksScope; task?: string; newTask?: boolean },
): string {
  const search = new URLSearchParams();
  if (params?.view && params.view !== 'current') search.set('view', params.view);
  if (params?.task) search.set('task', params.task);
  if (params?.newTask) search.set('new', '1');
  const qs = search.toString();
  return `/workspace/${encodeURIComponent(workspaceId)}/tasks${qs ? `?${qs}` : ''}`;
}

// -- API ------------------------------------------------------------------------

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    cache: 'no-store',
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    const detail = typeof body.detail === 'string' ? body.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const q = (params: Record<string, string | boolean | undefined>) => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === false) continue;
    search.set(key, String(value));
  }
  return search.toString();
};

export const tasksApi = {
  getSettings: (workspaceId: string) =>
    call<TasksSettings>(`/api/tasks/settings?${q({ workspace_id: workspaceId })}`),
  saveSettings: (
    workspaceId: string,
    settings: Pick<
      TasksSettings,
      | 'iteration_weeks'
      | 'iteration_start_day'
      | 'stages'
      | 'priorities'
      | 'default_stage'
      | 'suggested_labels'
      | 'feed_enabled'
      | 'feed_events'
      | 'feed_limit'
    >,
    today: string,
  ) =>
    call<TasksSettings>(`/api/tasks/settings?${q({ workspace_id: workspaceId })}`, {
      method: 'PUT',
      body: JSON.stringify({ ...settings, today }),
    }),
  listIterations: (workspaceId: string) =>
    call<TaskIteration[]>(`/api/tasks/iterations?${q({ workspace_id: workspaceId })}`),
  /** The iteration of the week ``date`` falls in, created when missing. */
  ensureIteration: (workspaceId: string, date: string) =>
    call<TaskIteration>(`/api/tasks/iterations?${q({ workspace_id: workspaceId })}`, {
      method: 'POST',
      body: JSON.stringify({ date }),
    }),
  updateGoal: (workspaceId: string, iterationId: string, goal: string) =>
    call<TaskIteration>(
      `/api/tasks/iterations/${encodeURIComponent(iterationId)}?${q({ workspace_id: workspaceId })}`,
      { method: 'PATCH', body: JSON.stringify({ goal }) },
    ),
  carryOver: (workspaceId: string, iterationId: string) =>
    call<{ iteration: TaskIteration; moved: Task[] }>(
      `/api/tasks/iterations/${encodeURIComponent(iterationId)}/carry-over?${q({ workspace_id: workspaceId })}`,
      { method: 'POST' },
    ),
  /** Every task of the workspace, newest first. */
  listAllTasks: (workspaceId: string, includeArchived = false) =>
    call<Task[]>(
      `/api/tasks?${q({ workspace_id: workspaceId, include_archived: includeArchived })}`,
    ),
  createTask: (workspaceId: string, fields: TaskFields & { title: string }) =>
    call<Task>(`/api/tasks?${q({ workspace_id: workspaceId })}`, {
      method: 'POST',
      body: JSON.stringify(fields),
    }),
  updateTask: (workspaceId: string, taskId: string, fields: TaskFields) =>
    call<Task>(`/api/tasks/${encodeURIComponent(taskId)}?${q({ workspace_id: workspaceId })}`, {
      method: 'PATCH',
      body: JSON.stringify(fields),
    }),
  archiveTask: (workspaceId: string, taskId: string) =>
    call<Task>(
      `/api/tasks/${encodeURIComponent(taskId)}/archive?${q({ workspace_id: workspaceId })}`,
      { method: 'POST' },
    ),
  restoreTask: (workspaceId: string, taskId: string) =>
    call<Task>(
      `/api/tasks/${encodeURIComponent(taskId)}/restore?${q({ workspace_id: workspaceId })}`,
      { method: 'POST' },
    ),
  deleteTask: (workspaceId: string, taskId: string) =>
    call<void>(`/api/tasks/${encodeURIComponent(taskId)}?${q({ workspace_id: workspaceId })}`, {
      method: 'DELETE',
    }),
  listComments: (workspaceId: string, taskId: string) =>
    call<TaskComment[]>(
      `/api/tasks/${encodeURIComponent(taskId)}/comments?${q({ workspace_id: workspaceId })}`,
    ),
  addComment: (workspaceId: string, taskId: string, body: string, parentId?: string) =>
    call<TaskComment>(
      `/api/tasks/${encodeURIComponent(taskId)}/comments?${q({ workspace_id: workspaceId })}`,
      { method: 'POST', body: JSON.stringify({ body, parent_id: parentId ?? null }) },
    ),
  /** Removes the comment and its replies (its author, or an owner or admin). */
  deleteComment: (workspaceId: string, taskId: string, commentId: string) =>
    call<void>(
      `/api/tasks/${encodeURIComponent(taskId)}/comments/${encodeURIComponent(commentId)}?${q({ workspace_id: workspaceId })}`,
      { method: 'DELETE' },
    ),
  /** The workspace's latest task events, newest first, as the feed settings configure it. */
  listFeed: (workspaceId: string) =>
    call<TaskActivity[]>(`/api/tasks/feed?${q({ workspace_id: workspaceId })}`),
  listActivity: (workspaceId: string, taskId: string) =>
    call<TaskActivity[]>(
      `/api/tasks/${encodeURIComponent(taskId)}/activity?${q({ workspace_id: workspaceId })}`,
    ),
  /** Everyone who may be assigned: explicit and organization-inherited members. */
  listMembers: (workspaceId: string) =>
    call<TasksMember[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/members`),
};
