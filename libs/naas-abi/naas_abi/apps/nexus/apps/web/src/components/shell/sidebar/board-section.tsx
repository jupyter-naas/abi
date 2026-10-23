'use client';

import { useEffect, useMemo } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { LayoutGrid, SquareKanban } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth';
import { useBoardStore } from '@/stores/board';
import { useWorkspaceStore } from '@/stores/workspace';
import {
  SCOPE_LABELS,
  STAGE_LABELS,
  UNASSIGNED,
  boardPath,
  formatWeekRange,
  matchesAssignee,
  parseScope,
  scopeOfTask,
  toIsoDate,
  weekStart,
  type BoardStage,
} from '@/lib/board';
import { CollapsibleSection } from './collapsible-section';
import { OntologyMultiPicker, type OntologyPickerOption } from './ontology-multi-picker';
import { SidebarNewItem } from './sidebar-new-item';
import { getWorkspacePath } from './utils';

// board.css only loads on the board route: the sidebar colors its own dots.
const STAGE_DOT: Record<BoardStage, string> = {
  inbox: 'bg-slate-400',
  ready: 'bg-blue-500',
  in_progress: 'bg-amber-500',
  on_hold: 'bg-purple-500',
  review: 'bg-cyan-500',
  done: 'bg-green-500',
};

const createdOn = (value: string | null) =>
  value
    ? new Date(value.endsWith('Z') ? value : `${value}Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : '';

/**
 * Board dashboard: every task of the workspace, newest first, filtered by
 * assignee. The assignee filter is shared with the board page.
 */
export function BoardSection({ collapsed, detailOnly }: { collapsed: boolean; detailOnly?: boolean }) {
  const workspaceId = useWorkspaceStore((s) => s.currentWorkspaceId);
  const userId = useAuthStore((s) => s.user?.id ?? null);
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { load, tasks, members, iterations, assignees, toggleAssignee, clearAssignees, loaded, error } =
    useBoardStore();

  useEffect(() => {
    if (workspaceId) void load(workspaceId);
  }, [workspaceId, load]);

  const onBoard = pathname?.includes('/board') ?? false;
  const openTaskId = onBoard ? searchParams?.get('task') : null;
  const currentWeek = weekStart(toIsoDate(new Date()));
  const currentView = onBoard ? parseScope(searchParams?.get('view')) : 'current';

  const memberName = useMemo(() => {
    const byId = new Map(members.map((m) => [m.user_id, m.name || m.email || 'Former member']));
    return (id: string) => byId.get(id) ?? 'Former member';
  }, [members]);
  const iterationById = useMemo(() => new Map(iterations.map((i) => [i.id, i])), [iterations]);

  const shown = useMemo(
    () =>
      tasks
        .filter((t) => !t.archived && matchesAssignee(t, assignees))
        .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '')),
    [tasks, assignees],
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

  if (!workspaceId) return null;

  const pickerLabel =
    assignees.length === 0
      ? 'All assignees'
      : assignees.length === 1
        ? assignees[0] === UNASSIGNED
          ? 'Unassigned'
          : memberName(assignees[0])
        : `${assignees.length} assignees`;
  const whereLabel = (iterationId: string | null, scope: ReturnType<typeof scopeOfTask>) => {
    if (scope) return SCOPE_LABELS[scope];
    const iteration = iterationId ? iterationById.get(iterationId) : undefined;
    return iteration ? formatWeekRange(iteration.start_date, iteration.end_date) : 'Another iteration';
  };

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
      <SidebarNewItem
        label="New task"
        title="New task in the board tab you are on"
        onClick={() => router.push(boardPath(workspaceId, { view: currentView, newTask: true }))}
      />
      <Link
        href={boardPath(workspaceId, { view: currentView })}
        aria-current={onBoard && !openTaskId ? 'page' : undefined}
        className="shell-sidebar-home"
      >
        <LayoutGrid size={14} aria-hidden="true" />
        <span>Dashboard</span>
      </Link>
      <div className="shell-sidebar-home-gutter pb-2 pt-1">
        <OntologyMultiPicker
          key={workspaceId}
          items={assigneeOptions}
          value={assignees}
          onToggle={toggleAssignee}
          onClear={clearAssignees}
          loading={!loaded}
          error={null}
          label={pickerLabel}
          allLabel="All assignees"
          noun="assignees"
        />
      </div>

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
              const scope = scopeOfTask(task, (id) => iterationById.get(id)?.start_date ?? null, currentWeek);
              const view = scope ?? currentView;
              const names = task.assignee_ids.map(memberName);
              return (
                <Link
                  key={task.id}
                  href={boardPath(workspaceId, { view, task: task.id })}
                  title={`${STAGE_LABELS[task.stage]}${names.length ? ` · ${names.join(', ')}` : ''}`}
                  className={cn(
                    'flex w-full items-start gap-2 px-2 py-1.5 text-sm transition-colors',
                    openTaskId === task.id
                      ? 'bg-muted font-medium text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )}
                >
                  <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', STAGE_DOT[task.stage])} />
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
    </CollapsibleSection>
  );
}
