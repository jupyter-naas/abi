'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { History, LayoutGrid, SquareKanban } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useTasksStore } from '@/stores/tasks';
import { useWorkspaceStore } from '@/stores/workspace';
import { describeTaskEvent } from '@/lib/task-events';
import {
  SCOPE_LABELS,
  UNASSIGNED,
  tasksPath,
  formatWeekRange,
  matchesFilters,
  NO_LABEL,
  NO_PRIORITY,
  parseScope,
  choiceColor,
  choiceLabel,
  scopeIterations,
  scopeOfTask,
  toIsoDate,
  type TaskActivity,
  type TaskColor,
  type TasksFilterKind,
} from '@/lib/tasks';
import { CollapsibleSection } from './collapsible-section';
import { OntologyMultiPicker, type OntologyPickerOption } from './ontology-multi-picker';
import { SidebarNewItem } from './sidebar-new-item';
import { getWorkspacePath } from './utils';

// tasks.css only loads on the tasks route: the sidebar colors its own dots.
const DOT: Record<TaskColor, string> = {
  slate: 'bg-slate-400',
  blue: 'bg-blue-500',
  amber: 'bg-amber-500',
  purple: 'bg-purple-500',
  cyan: 'bg-cyan-500',
  green: 'bg-green-500',
  red: 'bg-red-500',
  orange: 'bg-orange-500',
  yellow: 'bg-yellow-500',
  pink: 'bg-pink-500',
};

/** Other people's changes show up within this delay (and on every change made here). */
const FEED_REFRESH_MS = 60_000;

const toDate = (value: string) => new Date(value.endsWith('Z') ? value : `${value}Z`);

/** "just now", "5 min ago", "3 h ago", "yesterday", then the date. */
function timeAgo(value: string | null, now: number): string {
  if (!value) return '';
  const date = toDate(value);
  const minutes = Math.floor((now - date.getTime()) / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} h ago`;
  if (minutes < 48 * 60) return 'yesterday';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

const createdOn = (value: string | null) =>
  value
    ? new Date(value.endsWith('Z') ? value : `${value}Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : '';

/**
 * Tasks dashboard: the workspace's latest task events (created, changed,
 * deleted, commented), newest first, or every task when the feed is turned off
 * in the tasks settings. The assignee, priority and label filters are shared
 * with the Tasks page.
 */
export function TasksSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const userId = useAuthStore((s) => s.user?.id ?? null);
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    load,
    settings,
    tasks,
    members,
    iterations,
    filters,
    toggleFilter,
    clearFilter,
    loaded,
    error,
    feed,
    refreshFeed,
  } = useTasksStore();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (workspaceId) void load(workspaceId);
  }, [workspaceId, load]);

  // Picks up other people's events while the sidebar is open (and ages "5 min ago").
  useEffect(() => {
    if (!workspaceId || !settings.feed_enabled) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      setNow(Date.now());
      void refreshFeed();
    }, FEED_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [workspaceId, settings.feed_enabled, refreshFeed]);

  const onTasks = pathname?.includes('/tasks') ?? false;
  const openTaskId = onTasks ? searchParams?.get('task') : null;
  const scopes = useMemo(() => scopeIterations(iterations, toIsoDate(new Date())), [iterations]);
  const currentView = onTasks ? parseScope(searchParams?.get('view')) : 'current';

  const memberName = useMemo(() => {
    const byId = new Map(members.map((m) => [m.user_id, m.name || m.email || 'Former member']));
    return (id: string) => byId.get(id) ?? 'Former member';
  }, [members]);
  const iterationById = useMemo(() => new Map(iterations.map((i) => [i.id, i])), [iterations]);

  const shown = useMemo(
    () =>
      tasks
        .filter((t) => !t.archived && matchesFilters(t, filters))
        .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '')),
    [tasks, filters],
  );

  const taskById = useMemo(() => new Map(tasks.map((t) => [t.id, t])), [tasks]);
  const filtering = filters.assignees.length + filters.priorities.length + filters.labels.length > 0;
  /** Events of tasks the filters let through; a deleted task's events only show unfiltered. */
  const events = useMemo(
    () =>
      feed.filter((e) => {
        const task = taskById.get(e.task_id);
        return task ? matchesFilters(task, filters) : !filtering;
      }),
    [feed, taskById, filters, filtering],
  );
  const eventNames = useMemo(
    () => ({
      member: memberName,
      iteration: (id: string | null) => {
        const iteration = id ? iterationById.get(id) : undefined;
        return iteration ? formatWeekRange(iteration.start_date, iteration.end_date) : 'another iteration';
      },
      stage: (key: string) => choiceLabel(settings.stages, key),
      priority: (key: string) => choiceLabel(settings.priorities, key),
    }),
    [memberName, iterationById, settings.stages, settings.priorities],
  );

  const assigneeOptions = useMemo<OntologyPickerOption[]>(
    () => [
      { value: UNASSIGNED, label: 'Unassigned' },
      ...[...members]
        .sort((a, b) => (a.name || a.email || '').localeCompare(b.name || b.email || ''))
        .map((m) => ({
          value: m.user_id,
          label: `${m.name || m.email || 'Former member'}${m.user_id === userId ? ' (you)' : ''}`,
          detail: m.name && m.email ? m.email : undefined,
        })),
    ],
    [members, userId],
  );

  const priorityOptions = useMemo<OntologyPickerOption[]>(
    () => [
      ...settings.priorities.map((p) => ({ value: p.key, label: p.label })),
      { value: NO_PRIORITY, label: 'No priority' },
    ],
    [settings.priorities],
  );

  // Suggested labels first, then every other label already on a task.
  const labelOptions = useMemo<OntologyPickerOption[]>(() => {
    const used = tasks.flatMap((t) => t.labels).filter((l) => !settings.suggested_labels.includes(l));
    return [
      ...[...settings.suggested_labels, ...Array.from(new Set(used)).sort()].map((l) => ({ value: l, label: l })),
      { value: NO_LABEL, label: 'No label' },
    ];
  }, [tasks, settings.suggested_labels]);

  if (!workspaceId) return null;

  const pickers: { kind: TasksFilterKind; items: OntologyPickerOption[]; noun: string; allLabel: string }[] = [
    { kind: 'assignees', items: assigneeOptions, noun: 'assignees', allLabel: 'All assignees' },
    { kind: 'priorities', items: priorityOptions, noun: 'priorities', allLabel: 'All priorities' },
    { kind: 'labels', items: labelOptions, noun: 'labels', allLabel: 'All labels' },
  ];
  /** "All …", the one selected value's name, or "3 labels". */
  const pickerLabel = ({ kind, items, noun, allLabel }: (typeof pickers)[number]) => {
    const selected = filters[kind];
    if (selected.length === 0) return allLabel;
    if (selected.length > 1) return `${selected.length} ${noun}`;
    const option = items.find((o) => o.value === selected[0]);
    return kind === 'assignees' && !option ? memberName(selected[0]) : (option?.label ?? selected[0]);
  };
  const whereLabel = (iterationId: string | null, scope: ReturnType<typeof scopeOfTask>) => {
    if (scope) return SCOPE_LABELS[scope];
    const iteration = iterationId ? iterationById.get(iterationId) : undefined;
    return iteration ? formatWeekRange(iteration.start_date, iteration.end_date) : 'Another iteration';
  };

  return (
    <CollapsibleSection
      id="tasks"
      icon={<SquareKanban size={18} />}
      label="Tasks"
      description="Project tasks in weekly iterations"
      href={getWorkspacePath(workspaceId, '/tasks')}
      collapsed={collapsed}
      detailOnly={detailOnly}
    >
      <SidebarNewItem
        label="New task"
        title="New task in the Tasks tab you are on"
        onClick={() => router.push(tasksPath(workspaceId, { view: currentView, newTask: true }))}
      />
      <Link
        href={tasksPath(workspaceId, { view: currentView })}
        aria-current={onTasks && !openTaskId ? 'page' : undefined}
        className="shell-sidebar-home"
      >
        <LayoutGrid size={14} aria-hidden="true" />
        <span>Dashboard</span>
      </Link>
      <div className="shell-sidebar-home-gutter pb-2 pt-1">
        {pickers.map((picker) => (
          <OntologyMultiPicker
            key={`${picker.kind}:${workspaceId}`}
            items={picker.items}
            value={filters[picker.kind]}
            onToggle={(value) => toggleFilter(picker.kind, value)}
            onClear={() => clearFilter(picker.kind)}
            loading={!loaded}
            error={null}
            label={pickerLabel(picker)}
            allLabel={picker.allLabel}
            noun={picker.noun}
          />
        ))}
      </div>

      {settings.feed_enabled ? (
        <div className="shell-sidebar-home-gutter space-y-0.5">
          {!loaded ? (
            <p className="px-2 py-1 text-xs text-muted-foreground">Loading activity…</p>
          ) : events.length === 0 ? (
            <p className="px-2 py-1 text-xs text-muted-foreground">
              {feed.length ? 'No activity matches.' : 'No activity yet.'}
            </p>
          ) : (
            <>
              <p className="flex items-center gap-1 px-2 pb-1 text-[11px] text-muted-foreground">
                <History size={11} aria-hidden="true" /> Latest activity
              </p>
              {events.map((entry) => (
                <FeedItem
                  key={entry.id}
                  entry={entry}
                  actor={entry.actor_id ? memberName(entry.actor_id) : 'Someone'}
                  summary={describeTaskEvent(entry, eventNames, { withTask: true })}
                  when={timeAgo(entry.created_at, now)}
                  // A deleted task has nothing to open.
                  href={
                    taskById.has(entry.task_id)
                      ? tasksPath(workspaceId, {
                          view: scopeOfTask(taskById.get(entry.task_id)!, scopes) ?? currentView,
                          task: entry.task_id,
                        })
                      : null
                  }
                  active={openTaskId === entry.task_id}
                />
              ))}
            </>
          )}
        </div>
      ) : (
        <div className="shell-sidebar-home-gutter space-y-0.5">
          {!loaded ? (
            <p className="px-2 py-1 text-xs text-muted-foreground">Loading tasks…</p>
          ) : error && tasks.length === 0 ? (
            <p className="px-2 py-1 text-xs text-destructive">{error}</p>
          ) : shown.length === 0 ? (
            <p className="px-2 py-1 text-xs text-muted-foreground">
              {tasks.some((t) => !t.archived) ? 'No task matches.' : 'No tasks yet.'}
            </p>
          ) : (
            <>
              <p className="px-2 pb-1 text-[11px] text-muted-foreground">
                {shown.length} {shown.length === 1 ? 'task' : 'tasks'}, newest first
              </p>
              {shown.map((task) => {
                const scope = scopeOfTask(task, scopes);
                const view = scope ?? currentView;
                const names = task.assignee_ids.map(memberName);
                return (
                  <Link
                    key={task.id}
                    href={tasksPath(workspaceId, { view, task: task.id })}
                    title={`${choiceLabel(settings.stages, task.stage)}${names.length ? ` · ${names.join(', ')}` : ''}`}
                    className={cn(
                      'flex w-full items-start gap-2 px-2 py-1.5 text-sm transition-colors',
                      openTaskId === task.id
                        ? 'bg-muted font-medium text-foreground'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                    )}
                  >
                    <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', DOT[choiceColor(settings.stages, task.stage)])} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{task.title}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {whereLabel(task.iteration_id, scope)} · {createdOn(task.created_at)}
                        {names.length > 0 && ` · ${names.join(', ')}`}
                      </span>
                    </span>
                  </Link>
                );
              })}
            </>
          )}
        </div>
      )}
    </CollapsibleSection>
  );
}

function FeedItem({
  entry,
  actor,
  summary,
  when,
  href,
  active,
}: {
  entry: TaskActivity;
  actor: string;
  summary: string;
  when: string;
  href: string | null;
  active: boolean;
}) {
  const body = (
    <span className="min-w-0 flex-1">
      <span className="line-clamp-2 break-words">
        <span className="font-medium text-foreground">{actor}</span> {summary}
      </span>
      <span className="block text-xs text-muted-foreground" title={entry.created_at ?? undefined}>
        {when}
      </span>
    </span>
  );
  const className = cn(
    'flex w-full items-start gap-2 px-2 py-1.5 text-sm transition-colors',
    active ? 'bg-muted text-foreground' : 'text-muted-foreground',
  );
  return href ? (
    <Link href={href} className={cn(className, !active && 'hover:bg-muted hover:text-foreground')}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}
