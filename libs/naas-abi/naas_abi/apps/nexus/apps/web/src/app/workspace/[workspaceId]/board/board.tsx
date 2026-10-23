'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { CalendarDays, Columns3, Flag, LayoutGrid, Plus, SquareKanban, Table2, Tag, UserRound, X } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import { ViewBar, type ViewTypeDef } from '@/components/database-view/view-bar';
import { DatabaseBody } from '@/components/database-view/views';
import { useDatabaseViews } from '@/components/database-view/use-database-views';
import type { RecordGroup } from '@/components/database-view/model';
import {
  BOARD_SCOPES,
  DONE_STAGE,
  INBOX_STAGE,
  NO_LABEL,
  NO_PRIORITY,
  SCOPE_LABELS,
  UNASSIGNED,
  boardPath,
  boardSettingsPath,
  choiceColor,
  choiceFromLabel,
  choiceLabel,
  formatWeekRange,
  parseScope,
  toIsoDate,
  type BoardScope,
  type BoardSettings,
  type BoardTask,
  type TaskFields,
} from '@/lib/board';
import {
  BACKLOG_VIEWS,
  INBOX_VIEWS,
  ITERATION_VIEWS,
  TASK_VIEW_TYPE_LABELS,
  createTaskSchema,
  type TaskPropertyKey,
  type TaskViewType,
} from './lib/task-schema';
import { useBoard } from './lib/use-board';
import { IterationBar } from './components/iteration-bar';
import { ScopeTabs } from './components/scope-tabs';
import { BoardMenuBar } from './components/board-menu-bar';
import { TaskCard, TaskPropertyValue } from './components/task-card';
import { TaskDrawer } from './components/task-drawer';
import './board.css';

const VIEW_TYPES: ViewTypeDef<TaskViewType>[] = [
  { type: 'board', label: TASK_VIEW_TYPE_LABELS.board, icon: Columns3 },
  { type: 'table', label: TASK_VIEW_TYPE_LABELS.table, icon: Table2 },
  { type: 'gallery', label: TASK_VIEW_TYPE_LABELS.gallery, icon: LayoutGrid },
  { type: 'calendar', label: TASK_VIEW_TYPE_LABELS.calendar, icon: CalendarDays },
];

/** Groupings whose columns a card can be dragged between. */
const DRAGGABLE_GROUPS: TaskPropertyKey[] = ['stage', 'priority', 'project'];

/** What dropping a card on a board column changes, per grouping property. */
function fieldsForGroup(
  settings: BoardSettings,
  groupBy: TaskPropertyKey | null,
  groupKey: string,
): TaskFields | null {
  const empty = groupKey === '__empty__';
  if (groupBy === 'stage') {
    const stage = choiceFromLabel(settings.stages, groupKey);
    return stage ? { stage } : null;
  }
  if (groupBy === 'priority') return { priority: empty ? null : choiceFromLabel(settings.priorities, groupKey) };
  if (groupBy === 'project') return { project: empty ? '' : groupKey };
  return null;
}

/** The viewer's tab order, per workspace (a browser convenience, not shared). */
function useTabOrder(workspaceId: string) {
  const key = `nexus.board.tab-order.${workspaceId}`;
  const [order, setOrder] = useState<BoardScope[]>(BOARD_SCOPES);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(key) ?? 'null') as unknown;
      if (Array.isArray(saved)) {
        const known = saved.filter((s): s is BoardScope => BOARD_SCOPES.includes(s as BoardScope));
        setOrder([...new Set([...known, ...BOARD_SCOPES])]);
        return;
      }
    } catch {
      // Unavailable or corrupt storage: the default order.
    }
    setOrder(BOARD_SCOPES);
  }, [key]);
  const save = useCallback(
    (next: BoardScope[]) => {
      setOrder(next);
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // The order then lasts for this visit only.
      }
    },
    [key],
  );
  return [order, save] as const;
}

/** Local calendar day of a UTC timestamp from the API. */
function createdDay(timestamp: string): string {
  return toIsoDate(new Date(timestamp.endsWith('Z') ? timestamp : `${timestamp}Z`));
}

function ColumnAdd({ onCreate }: { onCreate: (title: string) => Promise<unknown> }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  if (!open) {
    return (
      <button type="button" className="board-column-add" onClick={() => setOpen(true)}>
        <Plus size={12} /> New task
      </button>
    );
  }
  const submit = () => {
    const value = title.trim();
    setTitle('');
    if (!value) {
      setOpen(false);
      return;
    }
    void onCreate(value).catch(() => undefined);
  };
  return (
    <input
      autoFocus
      className="board-column-add-input"
      value={title}
      maxLength={300}
      placeholder="Task title, then Enter"
      onChange={(e) => setTitle(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') submit();
        if (e.key === 'Escape') {
          setTitle('');
          setOpen(false);
        }
      }}
      onBlur={() => {
        if (title.trim()) submit();
        setOpen(false);
      }}
    />
  );
}

export default function BoardPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const searchParams = useSearchParams();
  const router = useRouter();
  const { confirm, dialog: confirmDialog } = useConfirm();
  const { prompt, dialog: promptDialog } = usePrompt();

  const scope = parseScope(searchParams?.get('view'));
  const openTaskId = searchParams?.get('task') ?? null;
  const isIteration = scope === 'current' || scope === 'last' || scope === 'next';
  const [showArchived, setShowArchived] = useState(false);
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState<{ text: string; scope?: BoardScope } | null>(null);

  const board = useBoard(workspaceId, scope, showArchived);
  const [tabOrder, setTabOrder] = useTabOrder(workspaceId);

  const navigate = useCallback(
    (next: { view?: BoardScope; task?: string | null }) => {
      router.replace(
        boardPath(workspaceId, {
          view: next.view ?? scope,
          task: next.task === null ? undefined : next.task ?? openTaskId ?? undefined,
        }),
      );
    },
    [router, workspaceId, scope, openTaskId],
  );

  const iterationById = useMemo(() => new Map(board.iterations.map((i) => [i.id, i])), [board.iterations]);
  const iterationLabel = useCallback(
    (iterationId: string) => {
      const iteration = iterationById.get(iterationId);
      if (!iteration) return 'Another iteration';
      const range = formatWeekRange(iteration.start_date, iteration.end_date);
      return iteration.id === board.currentIteration?.id ? `${range} (current)` : range;
    },
    [iterationById, board.currentIteration],
  );

  const { settings } = board;
  const schema = useMemo(
    () => createTaskSchema({ memberName: board.memberName, iterationLabel, settings }),
    [board.memberName, iterationLabel, settings],
  );
  const iterationViews = useDatabaseViews(workspaceId, ITERATION_VIEWS);
  const inboxViews = useDatabaseViews(workspaceId, INBOX_VIEWS);
  const backlogViews = useDatabaseViews(workspaceId, BACKLOG_VIEWS);
  const viewsFor = (target: BoardScope) =>
    target === 'inbox' ? inboxViews : target === 'backlog' ? backlogViews : iterationViews;
  const views = viewsFor(scope);
  const view = views.activeView;
  const groupBy = view.type === 'board' ? view.groupBy ?? 'stage' : view.groupBy;

  const groups = useMemo(() => {
    const rows = schema.applySort(
      schema.applySearch(schema.applyFilters(board.tasks, view.filters), search),
      view.sort,
    );
    // Grouping on the sorted property follows the sort's direction (Inbox: newest day first).
    const grouped = schema.groupRecords(
      rows,
      groupBy,
      view.sort && view.sort.property === groupBy ? view.sort.direction : 'asc',
    );
    // Inbox has its own tab: iteration columns start after it.
    const inboxLabel = choiceLabel(settings.stages, INBOX_STAGE);
    return isIteration && groupBy === 'stage' ? grouped.filter((g) => g.key !== inboxLabel) : grouped;
  }, [schema, board.tasks, view.filters, view.sort, search, groupBy, isIteration, settings.stages]);
  const visibleCount = useMemo(
    () => new Set(groups.flatMap((g) => g.records.map((t) => t.id))).size,
    [groups],
  );

  const projects = useMemo(
    () => Array.from(new Set(board.allTasks.map((t) => t.project).filter(Boolean))).sort(),
    [board.allTasks],
  );
  const labels = useMemo(
    () => Array.from(new Set(board.allTasks.flatMap((t) => t.labels))).sort(),
    [board.allTasks],
  );

  const openTask = board.allTasks.find((t) => t.id === openTaskId) ?? null;

  const handleNewTask = async () => {
    const title = await prompt({
      title: 'New task',
      description:
        scope === 'inbox'
          ? 'Added to Inbox for triage.'
          : scope === 'backlog'
            ? 'Added to the backlog as Ready.'
            : `Added to ${SCOPE_LABELS[scope].toLowerCase()} as Ready.`,
      placeholder: 'Task title',
      confirmLabel: 'Create',
    });
    if (!title?.trim()) return;
    try {
      const created = await board.createTask({ title: title.trim() });
      navigate({ task: created.id });
    } catch {
      // Shown in the error banner.
    }
  };

  // The sidebar's "New task" opens the board with ?new=1.
  const newRequested = searchParams?.get('new') === '1';
  const handleNewTaskRef = useRef(handleNewTask);
  handleNewTaskRef.current = handleNewTask;
  const newHandled = useRef(false);
  useEffect(() => {
    if (!newRequested) {
      newHandled.current = false;
      return;
    }
    if (newHandled.current) return;
    newHandled.current = true;
    router.replace(boardPath(workspaceId, { view: scope, task: openTaskId ?? undefined }));
    void handleNewTaskRef.current();
  }, [newRequested, router, workspaceId, scope, openTaskId]);

  const handleDropOnScope = async (taskId: string, target: BoardScope) => {
    const task = board.allTasks.find((t) => t.id === taskId);
    if (!task) return;
    try {
      if (await board.moveToScope(task, target)) {
        setNotice({ text: `Moved "${task.title}" to ${SCOPE_LABELS[target]}.`, scope: target });
      }
    } catch {
      // Shown in the error banner.
    }
  };

  const handleCarryOver = async () => {
    try {
      const result = await board.carryOver();
      if (!result) return;
      const target: BoardScope = scope === 'last' ? 'current' : 'next';
      setNotice(
        result.moved === 0
          ? { text: 'Every task is Done: nothing to move.' }
          : {
              text: `Moved ${result.moved} unfinished ${result.moved === 1 ? 'task' : 'tasks'} to ${SCOPE_LABELS[target].toLowerCase()}.`,
              scope: target,
            },
      );
    } catch {
      // Shown in the error banner.
    }
  };

  const handleDelete = async (task: BoardTask) => {
    const ok = await confirm({
      title: 'Delete task?',
      description: `"${task.title}" and its comments and history are deleted for everyone. Archive it instead to keep it recoverable.`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    try {
      await board.deleteTask(task.id);
      navigate({ task: null });
    } catch {
      // Shown in the error banner.
    }
  };

  const canDrag = view.type === 'board' && !!groupBy && DRAGGABLE_GROUPS.includes(groupBy);
  const filterChips = [
    {
      kind: 'assignees' as const,
      icon: UserRound,
      plural: 'assignees',
      names: board.filters.assignees.map((id) => (id === UNASSIGNED ? 'Unassigned' : board.memberName(id))),
    },
    {
      kind: 'priorities' as const,
      icon: Flag,
      plural: 'priorities',
      names: board.filters.priorities.map((key) =>
        key === NO_PRIORITY ? 'No priority' : choiceLabel(settings.priorities, key),
      ),
    },
    {
      kind: 'labels' as const,
      icon: Tag,
      plural: 'labels',
      names: board.filters.labels.map((label) => (label === NO_LABEL ? 'No label' : label)),
    },
  ].filter((chip) => chip.names.length > 0);

  return (
    <div className="board-page">
      <Header
        title="Board"
        subtitle="Project tasks in weekly iterations"
        nav={
          <BoardMenuBar
            onNewTask={() => void handleNewTask()}
            onSettings={() => router.push(boardSettingsPath(workspaceId))}
          />
        }
      />
      {confirmDialog}
      {promptDialog}

      {board.error && (
        <div className="board-error" role="alert">
          <span>{board.error}</span>
          <button type="button" className="board-error-dismiss" title="Dismiss" onClick={board.clearError}>
            <X size={12} />
          </button>
        </div>
      )}
      {notice && (
        <div className="board-notice" role="status">
          <span>{notice.text}</span>
          <span className="board-notice-actions">
            {notice.scope && notice.scope !== scope && (
              <button
                type="button"
                className="board-notice-link"
                onClick={() => {
                  setNotice(null);
                  navigate({ view: notice.scope, task: null });
                }}
              >
                Open {SCOPE_LABELS[notice.scope].toLowerCase()}
              </button>
            )}
            <button type="button" className="board-error-dismiss" title="Dismiss" onClick={() => setNotice(null)}>
              <X size={12} />
            </button>
          </span>
        </div>
      )}

      <IterationBar
        scope={scope}
        day={board.day}
        iteration={board.iteration}
        showArchived={showArchived}
        canCarryOver={board.tasks.some((t) => t.stage !== DONE_STAGE && !t.archived)}
        onToggleArchived={() => setShowArchived((v) => !v)}
        onSaveGoal={(goal) => void board.setGoal(goal).catch(() => undefined)}
        onCarryOver={() => void handleCarryOver()}
      />

      <ViewBar
        api={views}
        schema={schema}
        viewTypes={VIEW_TYPES}
        records={board.tasks}
        search={search}
        onSearchChange={setSearch}
        count={visibleCount}
        countLabel={(n) => `${n} ${n === 1 ? 'task' : 'tasks'}`}
        defaultFilterProperty="project"
        groupedTypes={['board']}
        defaultGroupBy="stage"
        iconOnly
        tabs={
          <ScopeTabs
            order={tabOrder}
            onReorder={setTabOrder}
            active={scope}
            counts={board.counts}
            layouts={VIEW_TYPES}
            layoutOf={(target) => viewsFor(target).activeView.type}
            onChangeLayout={(type) =>
              views.updateActiveView({ type, groupBy: type === 'board' ? view.groupBy ?? 'stage' : view.groupBy })
            }
            onSelect={(next) => navigate({ view: next, task: null })}
            onDropTask={(taskId, target) => void handleDropOnScope(taskId, target)}
          />
        }
        actions={
          <>
            {filterChips.map(({ kind, icon: Icon, plural, names }) => (
              <span
                key={kind}
                className="board-filter-chip"
                title={`Set from the Board dashboard in the sidebar: ${names.join(', ')}`}
              >
                <Icon size={12} />
                <span className="board-filter-chip-label">
                  {names.length === 1 ? names[0] : `${names.length} ${plural}`}
                </span>
                <button
                  type="button"
                  className="board-filter-chip-clear"
                  title={`Show every ${plural === 'priorities' ? 'priority' : plural.slice(0, -1)}`}
                  onClick={() => board.clearFilter(kind)}
                >
                  <X size={11} />
                </button>
              </span>
            ))}
          </>
        }
      />

      <div className="board-page-scroll">
        {board.loading ? (
          <div className="board-empty">
            <SquareKanban size={18} className="animate-pulse" /> Loading board…
          </div>
        ) : (view.type === 'table' || view.type === 'gallery') && visibleCount === 0 ? (
          <div className="board-empty">
            <p className="board-empty-title">{board.tasks.length ? 'No task matches' : 'No tasks yet'}</p>
            <p>
              {board.tasks.length
                ? 'Change the search or the filters to see more tasks.'
                : scope === 'inbox'
                  ? 'New requests land here until someone triages them.'
                  : scope === 'backlog'
                    ? 'Drag a task onto the Backlog tab to keep it for later.'
                    : 'Create a task or drag one onto this tab.'}
            </p>
          </div>
        ) : (
          <DatabaseBody
            schema={schema}
            view={{ ...view, groupBy }}
            groups={groups}
            getId={(task) => task.id}
            onOpen={(task) => navigate({ task: task.id })}
            draggableRows
            fitColumns
            calendar={
              scope === 'inbox'
                ? { getDate: (task) => (task.created_at ? createdDay(task.created_at) : null), dateLabel: 'Created date' }
                : {
                    getDate: (task) => task.due_date,
                    dateLabel: 'Due date',
                    onMoveToDate: (task, day) => void board.updateTask(task.id, { due_date: day }).catch(() => undefined),
                  }
            }
            renderCard={(task, visible) => (
              <TaskCard
                task={task}
                visible={visible}
                schema={schema}
                priorities={settings.priorities}
                today={board.today}
                onOpen={() => navigate({ task: task.id })}
              />
            )}
            renderValue={(task, key) => (
              <TaskPropertyValue
                task={task}
                propertyKey={key}
                schema={schema}
                priorities={settings.priorities}
                today={board.today}
              />
            )}
            renderLeading={(task) => (
              <span className={`board-stage-dot board-dot-${choiceColor(settings.stages, task.stage)}`} />
            )}
            renderColumnMarker={
              groupBy === 'stage'
                ? (group: RecordGroup<BoardTask>) => {
                    const stage = choiceFromLabel(settings.stages, group.key);
                    return stage ? (
                      <span className={`board-stage-dot board-dot-${choiceColor(settings.stages, stage)}`} />
                    ) : null;
                  }
                : undefined
            }
            onMoveToGroup={
              canDrag
                ? (task, groupKey) => {
                    const fields = fieldsForGroup(settings, groupBy, groupKey);
                    if (fields) void board.updateTask(task.id, fields).catch(() => undefined);
                  }
                : undefined
            }
            renderColumnFooter={
              isIteration && groupBy === 'stage'
                ? (group) => {
                    const stage = choiceFromLabel(settings.stages, group.key);
                    return stage ? (
                      <ColumnAdd onCreate={(title) => board.createTask({ title, stage })} />
                    ) : null;
                  }
                : undefined
            }
          />
        )}
      </div>

      {openTask && (
        <TaskDrawer
          key={openTask.id}
          workspaceId={workspaceId}
          task={openTask}
          iterations={board.iterations}
          iterationLabel={iterationLabel}
          members={board.members}
          memberName={board.memberName}
          projects={projects}
          labels={labels}
          settings={settings}
          onUpdate={(fields) => board.updateTask(openTask.id, fields)}
          onArchive={(archived) => board.setArchived(openTask.id, archived)}
          onDelete={() => handleDelete(openTask)}
          onClose={() => navigate({ task: null })}
        />
      )}
    </div>
  );
}
