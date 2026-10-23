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
  UNASSIGNED,
  boardPath,
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
  type BoardColor,
  type BoardFilterKind,
} from '@/lib/board';
import { CollapsibleSection } from './collapsible-section';
import { OntologyMultiPicker, type OntologyPickerOption } from './ontology-multi-picker';
import { SidebarNewItem } from './sidebar-new-item';
import { getWorkspacePath } from './utils';

// board.css only loads on the board route: the sidebar colors its own dots.
const DOT: Record<BoardColor, string> = {
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
  } = useBoardStore();

  useEffect(() => {
    if (workspaceId) void load(workspaceId);
  }, [workspaceId, load]);

  const onBoard = pathname?.includes('/board') ?? false;
  const openTaskId = onBoard ? searchParams?.get('task') : null;
  const scopes = useMemo(() => scopeIterations(iterations, toIsoDate(new Date())), [iterations]);
  const currentView = onBoard ? parseScope(searchParams?.get('view')) : 'current';

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

  const pickers: { kind: BoardFilterKind; items: OntologyPickerOption[]; noun: string; allLabel: string }[] = [
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
                  href={boardPath(workspaceId, { view, task: task.id })}
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
    </CollapsibleSection>
  );
}
