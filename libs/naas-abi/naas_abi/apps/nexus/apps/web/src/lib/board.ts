/**
 * Workspace project board: weekly iterations, tasks, comments and activity.
 *
 * API: /api/board (see services/board in the API). An iteration is one ISO
 * week, Monday through Sunday, keyed by its Monday. The board asks for "the
 * iteration of this date" with the user's local date, so the week boundary
 * follows the user's timezone.
 *
 * The page shows five scopes: the current, last and next iterations (their
 * tasks past Inbox), Inbox (every task waiting for triage, scheduled or not)
 * and Backlog (triaged tasks without an iteration).
 */
import { authFetch } from '@/stores/auth';

export type BoardStage = 'inbox' | 'ready' | 'in_progress' | 'on_hold' | 'review' | 'done';
export type BoardPriority = 'urgent' | 'high' | 'medium' | 'low';

export const BOARD_STAGES: BoardStage[] = ['inbox', 'ready', 'in_progress', 'on_hold', 'review', 'done'];
export const BOARD_PRIORITIES: BoardPriority[] = ['urgent', 'high', 'medium', 'low'];

export const STAGE_LABELS: Record<BoardStage, string> = {
  inbox: 'Inbox',
  ready: 'Ready',
  in_progress: 'In progress',
  on_hold: 'On hold',
  review: 'Review',
  done: 'Done',
};

export const PRIORITY_LABELS: Record<BoardPriority, string> = {
  urgent: 'Urgent',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

/** Label suggestions; any label can be typed. */
export const SUGGESTED_LABELS = ['Feature', 'Bug', 'Data', 'Model', 'Research', 'Chore'];

export function stageFromLabel(label: string): BoardStage | null {
  return BOARD_STAGES.find((stage) => STAGE_LABELS[stage] === label) ?? null;
}

export function priorityFromLabel(label: string): BoardPriority | null {
  return BOARD_PRIORITIES.find((priority) => PRIORITY_LABELS[priority] === label) ?? null;
}

export type BoardIteration = {
  id: string;
  workspace_id: string;
  /** YYYY-MM-DD, a Monday. */
  start_date: string;
  /** YYYY-MM-DD, the Sunday after. */
  end_date: string;
  /** e.g. 2026-W43 */
  iso_week: string;
  goal: string;
  created_by: string | null;
  created_at: string | null;
  updated_by: string | null;
  updated_at: string | null;
};

export type BoardTask = {
  id: string;
  workspace_id: string;
  title: string;
  content: string;
  stage: BoardStage;
  iteration_id: string | null;
  project: string;
  priority: BoardPriority | null;
  due_date: string | null;
  labels: string[];
  assignee_ids: string[];
  archived: boolean;
  archived_at: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_by: string | null;
  updated_at: string | null;
};

export type BoardComment = {
  id: string;
  task_id: string;
  author_id: string | null;
  body: string;
  created_at: string;
};

export type BoardActivityField = 'created' | 'stage' | 'assignees' | 'iteration' | 'archived';

export type BoardActivity = {
  id: string;
  task_id: string;
  actor_id: string | null;
  field: BoardActivityField | string;
  old_value: unknown;
  new_value: unknown;
  created_at: string | null;
};

export type BoardMember = {
  user_id: string;
  name: string | null;
  email: string | null;
  role: string;
};

export type TaskFields = Partial<
  Pick<
    BoardTask,
    'title' | 'content' | 'stage' | 'iteration_id' | 'project' | 'priority' | 'due_date' | 'labels' | 'assignee_ids'
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

/** Relative name of a week from today's week: "Current iteration", "Next iteration"… */
export function iterationName(start: string, today: string): string {
  const current = weekStart(today);
  if (start === current) return 'Current iteration';
  if (start === addWeeks(current, -1)) return 'Last iteration';
  if (start === addWeeks(current, 1)) return 'Next iteration';
  return `Week of ${parseIsoDate(start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
}

// -- Scopes ---------------------------------------------------------------------

export type BoardScope = 'current' | 'last' | 'next' | 'inbox' | 'backlog';

export const BOARD_SCOPES: BoardScope[] = ['current', 'last', 'next', 'inbox', 'backlog'];

export const SCOPE_LABELS: Record<BoardScope, string> = {
  current: 'Current iteration',
  last: 'Last iteration',
  next: 'Next iteration',
  inbox: 'Inbox',
  backlog: 'Backlog',
};

export function parseScope(value: string | null | undefined): BoardScope {
  return BOARD_SCOPES.find((scope) => scope === value) ?? 'current';
}

/** Monday of the week an iteration scope shows; null for Inbox and Backlog. */
export function scopeWeek(scope: BoardScope, currentWeek: string): string | null {
  if (scope === 'current') return currentWeek;
  if (scope === 'last') return addWeeks(currentWeek, -1);
  if (scope === 'next') return addWeeks(currentWeek, 1);
  return null;
}

/**
 * Whether a task shows in a scope. ``iterationId`` is the scope's iteration
 * (null when that week has none yet). Inbox tasks only show in Inbox.
 */
export function taskInScope(task: BoardTask, scope: BoardScope, iterationId: string | null): boolean {
  if (scope === 'inbox') return task.stage === 'inbox';
  if (task.stage === 'inbox') return false;
  if (scope === 'backlog') return task.iteration_id === null;
  return iterationId !== null && task.iteration_id === iterationId;
}

/**
 * What dropping a task on a scope changes, or null when it is already there.
 * Leaving Inbox makes a task Ready; going to Inbox keeps its iteration, so it
 * returns there once triaged.
 */
export function fieldsForScope(task: BoardTask, scope: BoardScope, iterationId: string | null): TaskFields | null {
  if (taskInScope(task, scope, iterationId)) return null;
  if (scope === 'inbox') return { stage: 'inbox' };
  const stage = task.stage === 'inbox' ? { stage: 'ready' as const } : {};
  return { ...stage, iteration_id: scope === 'backlog' ? null : iterationId };
}

/** The scope a task shows in, or null for an iteration outside last/current/next. */
export function scopeOfTask(task: BoardTask, iterationWeek: (iterationId: string) => string | null, currentWeek: string): BoardScope | null {
  if (task.stage === 'inbox') return 'inbox';
  if (task.iteration_id === null) return 'backlog';
  const week = iterationWeek(task.iteration_id);
  return (['current', 'last', 'next'] as const).find((scope) => scopeWeek(scope, currentWeek) === week) ?? null;
}

/** Assignee filter value for tasks nobody is assigned to. */
export const UNASSIGNED = '__unassigned__';

/** ``assignees`` holds user ids and/or UNASSIGNED; empty means everyone. */
export function matchesAssignee(task: BoardTask, assignees: string[]): boolean {
  if (assignees.length === 0) return true;
  if (task.assignee_ids.length === 0) return assignees.includes(UNASSIGNED);
  return task.assignee_ids.some((id) => assignees.includes(id));
}

/** ``newTask`` opens the board's "New task" prompt on arrival. */
export function boardPath(
  workspaceId: string,
  params?: { view?: BoardScope; task?: string; newTask?: boolean },
): string {
  const search = new URLSearchParams();
  if (params?.view && params.view !== 'current') search.set('view', params.view);
  if (params?.task) search.set('task', params.task);
  if (params?.newTask) search.set('new', '1');
  const qs = search.toString();
  return `/workspace/${encodeURIComponent(workspaceId)}/board${qs ? `?${qs}` : ''}`;
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

export const boardApi = {
  listIterations: (workspaceId: string) =>
    call<BoardIteration[]>(`/api/board/iterations?${q({ workspace_id: workspaceId })}`),
  /** The iteration of the week ``date`` falls in, created when missing. */
  ensureIteration: (workspaceId: string, date: string) =>
    call<BoardIteration>(`/api/board/iterations?${q({ workspace_id: workspaceId })}`, {
      method: 'POST',
      body: JSON.stringify({ date }),
    }),
  updateGoal: (workspaceId: string, iterationId: string, goal: string) =>
    call<BoardIteration>(
      `/api/board/iterations/${encodeURIComponent(iterationId)}?${q({ workspace_id: workspaceId })}`,
      { method: 'PATCH', body: JSON.stringify({ goal }) },
    ),
  carryOver: (workspaceId: string, iterationId: string) =>
    call<{ iteration: BoardIteration; moved: BoardTask[] }>(
      `/api/board/iterations/${encodeURIComponent(iterationId)}/carry-over?${q({ workspace_id: workspaceId })}`,
      { method: 'POST' },
    ),
  /** Every task of the workspace, newest first. */
  listAllTasks: (workspaceId: string, includeArchived = false) =>
    call<BoardTask[]>(
      `/api/board/tasks?${q({ workspace_id: workspaceId, include_archived: includeArchived })}`,
    ),
  createTask: (workspaceId: string, fields: TaskFields & { title: string }) =>
    call<BoardTask>(`/api/board/tasks?${q({ workspace_id: workspaceId })}`, {
      method: 'POST',
      body: JSON.stringify(fields),
    }),
  updateTask: (workspaceId: string, taskId: string, fields: TaskFields) =>
    call<BoardTask>(`/api/board/tasks/${encodeURIComponent(taskId)}?${q({ workspace_id: workspaceId })}`, {
      method: 'PATCH',
      body: JSON.stringify(fields),
    }),
  archiveTask: (workspaceId: string, taskId: string) =>
    call<BoardTask>(
      `/api/board/tasks/${encodeURIComponent(taskId)}/archive?${q({ workspace_id: workspaceId })}`,
      { method: 'POST' },
    ),
  restoreTask: (workspaceId: string, taskId: string) =>
    call<BoardTask>(
      `/api/board/tasks/${encodeURIComponent(taskId)}/restore?${q({ workspace_id: workspaceId })}`,
      { method: 'POST' },
    ),
  deleteTask: (workspaceId: string, taskId: string) =>
    call<void>(`/api/board/tasks/${encodeURIComponent(taskId)}?${q({ workspace_id: workspaceId })}`, {
      method: 'DELETE',
    }),
  listComments: (workspaceId: string, taskId: string) =>
    call<BoardComment[]>(
      `/api/board/tasks/${encodeURIComponent(taskId)}/comments?${q({ workspace_id: workspaceId })}`,
    ),
  addComment: (workspaceId: string, taskId: string, body: string) =>
    call<BoardComment>(
      `/api/board/tasks/${encodeURIComponent(taskId)}/comments?${q({ workspace_id: workspaceId })}`,
      { method: 'POST', body: JSON.stringify({ body }) },
    ),
  listActivity: (workspaceId: string, taskId: string) =>
    call<BoardActivity[]>(
      `/api/board/tasks/${encodeURIComponent(taskId)}/activity?${q({ workspace_id: workspaceId })}`,
    ),
  /** Everyone who may be assigned: explicit and organization-inherited members. */
  listMembers: (workspaceId: string) =>
    call<BoardMember[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/members`),
};
