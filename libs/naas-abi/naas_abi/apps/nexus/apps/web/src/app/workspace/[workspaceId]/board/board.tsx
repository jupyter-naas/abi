'use client';

import { useCallback, useMemo, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Columns3, List, Plus, SquareKanban, Table2, X } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { useConfirm, usePrompt } from '@/components/ui/dialogs';
import { ViewBar, type ViewTypeDef } from '@/components/database-view/view-bar';
import { DatabaseBody } from '@/components/database-view/views';
import { useDatabaseViews } from '@/components/database-view/use-database-views';
import type { RecordGroup } from '@/components/database-view/model';
import {
  boardPath,
  formatWeekRange,
  priorityFromLabel,
  stageFromLabel,
  toIsoDate,
  weekStart,
  type BoardTask,
  type TaskFields,
} from '@/lib/board';
import { TASK_VIEWS, TASK_VIEW_TYPE_LABELS, createTaskSchema, type TaskPropertyKey, type TaskViewType } from './lib/task-schema';
import { useBoard, type BoardScope } from './lib/use-board';
import { IterationBar } from './components/iteration-bar';
import { TaskCard, TaskPropertyValue } from './components/task-card';
import { TaskDrawer } from './components/task-drawer';
import './board.css';

const VIEW_TYPES: ViewTypeDef<TaskViewType>[] = [
  { type: 'board', label: TASK_VIEW_TYPE_LABELS.board, icon: Columns3 },
  { type: 'table', label: TASK_VIEW_TYPE_LABELS.table, icon: Table2 },
  { type: 'list', label: TASK_VIEW_TYPE_LABELS.list, icon: List },
];

/** Groupings whose columns a card can be dragged between. */
const DRAGGABLE_GROUPS: TaskPropertyKey[] = ['stage', 'priority', 'project'];

/** What dropping a card on a board column changes, per grouping property. */
function fieldsForGroup(groupBy: TaskPropertyKey | null, groupKey: string): TaskFields | null {
  const empty = groupKey === '__empty__';
  if (groupBy === 'stage') {
    const stage = stageFromLabel(groupKey);
    return stage ? { stage } : null;
  }
  if (groupBy === 'priority') return { priority: empty ? null : priorityFromLabel(groupKey) };
  if (groupBy === 'project') return { project: empty ? '' : groupKey };
  return null;
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

  const backlog = searchParams?.get('backlog') === '1';
  const weekParam = searchParams?.get('week');
  const openTaskId = searchParams?.get('task') ?? null;
  const [showArchived, setShowArchived] = useState(false);
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState<string | null>(null);

  // The user's local date: the week boundary follows their timezone.
  const todayWeek = weekStart(toIsoDate(new Date()));
  const scope: BoardScope = backlog
    ? { kind: 'backlog' }
    : { kind: 'week', week: weekParam ? weekStart(weekParam) : todayWeek };
  const board = useBoard(workspaceId, scope, showArchived);
  const week = board.week ?? board.currentWeek;

  const navigate = useCallback(
    (next: { week?: string; backlog?: boolean; task?: string | null }) => {
      const nextBacklog = next.backlog ?? backlog;
      router.replace(
        boardPath(workspaceId, {
          backlog: nextBacklog,
          week: nextBacklog ? undefined : next.week ?? (weekParam ? week : undefined),
          task: next.task === null ? undefined : next.task ?? openTaskId ?? undefined,
        }),
      );
    },
    [router, workspaceId, backlog, weekParam, week, openTaskId],
  );

  const iterationById = useMemo(() => new Map(board.iterations.map((i) => [i.id, i])), [board.iterations]);
  const iterationLabel = useCallback(
    (iterationId: string) => {
      const iteration = iterationById.get(iterationId);
      if (!iteration) return 'Another iteration';
      const range = formatWeekRange(iteration.start_date, iteration.end_date);
      return iteration.start_date === board.currentWeek ? `${range} (current)` : range;
    },
    [iterationById, board.currentWeek],
  );

  const schema = useMemo(
    () => createTaskSchema({ memberName: board.memberName, iterationLabel }),
    [board.memberName, iterationLabel],
  );
  const views = useDatabaseViews(workspaceId, TASK_VIEWS);
  const view = views.activeView;
  const groupBy = view.type === 'board' ? view.groupBy ?? 'stage' : view.groupBy;

  const groups = useMemo(() => {
    const rows = schema.applySort(
      schema.applySearch(schema.applyFilters(board.tasks, view.filters), search),
      view.sort,
    );
    return schema.groupRecords(rows, groupBy);
  }, [schema, board.tasks, view.filters, view.sort, search, groupBy]);
  const visibleCount = useMemo(
    () => new Set(groups.flatMap((g) => g.records.map((t) => t.id))).size,
    [groups],
  );

  const projects = useMemo(
    () => Array.from(new Set(board.tasks.map((t) => t.project).filter(Boolean))).sort(),
    [board.tasks],
  );
  const labels = useMemo(
    () => Array.from(new Set(board.tasks.flatMap((t) => t.labels))).sort(),
    [board.tasks],
  );

  const openTask = board.tasks.find((t) => t.id === openTaskId) ?? null;
  const canCreate = backlog || !!board.iteration;

  const handleNewTask = async () => {
    const title = await prompt({
      title: 'New task',
      description: backlog ? 'Added to the backlog.' : 'Added to Inbox in this iteration.',
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

  const handleCarryOver = async () => {
    try {
      const result = await board.carryOver();
      if (!result) return;
      setNotice(
        result.moved === 0
          ? 'Every task is Done: nothing to move.'
          : `Moved ${result.moved} unfinished ${result.moved === 1 ? 'task' : 'tasks'} to next iteration.`,
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

  return (
    <div className="board-page">
      <Header title="Board" subtitle="Project tasks in weekly iterations" />
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
          <span>{notice}</span>
          <span className="board-notice-actions">
            <button
              type="button"
              className="board-notice-link"
              onClick={() => {
                setNotice(null);
                navigate({ week: board.nextWeek ?? undefined, backlog: false, task: null });
              }}
            >
              Open next iteration
            </button>
            <button type="button" className="board-error-dismiss" title="Dismiss" onClick={() => setNotice(null)}>
              <X size={12} />
            </button>
          </span>
        </div>
      )}

      <IterationBar
        backlog={backlog}
        week={week}
        today={board.today}
        iteration={board.iteration}
        showArchived={showArchived}
        canCarryOver={board.tasks.some((t) => t.stage !== 'done' && !t.archived)}
        onNavigateWeek={(next) => navigate({ week: next, task: null })}
        onToggleBacklog={() => navigate({ backlog: !backlog, week: undefined, task: null })}
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
        actions={
          <button
            type="button"
            className="board-button board-button-primary"
            disabled={!canCreate}
            onClick={() => void handleNewTask()}
          >
            <Plus size={13} /> New task
          </button>
        }
      />

      <div className="board-page-scroll">
        {board.loading ? (
          <div className="board-empty">
            <SquareKanban size={18} className="animate-pulse" /> Loading board…
          </div>
        ) : board.missingIteration ? (
          <div className="board-empty">
            <p className="board-empty-title">No iteration for this week yet</p>
            <p>Create it to plan this week&apos;s tasks. It uses the same stages as every iteration.</p>
            <button
              type="button"
              className="board-button board-button-primary"
              onClick={() => void board.createIteration().catch(() => undefined)}
            >
              <Plus size={13} /> Create iteration
            </button>
          </div>
        ) : view.type !== 'board' && visibleCount === 0 ? (
          <div className="board-empty">
            <p className="board-empty-title">{board.tasks.length ? 'No task matches' : 'No tasks yet'}</p>
            <p>
              {board.tasks.length
                ? 'Change the search or the filters to see more tasks.'
                : backlog
                  ? 'Ideas and requests that are not scheduled yet land here.'
                  : 'Create a task: it starts in Inbox.'}
            </p>
          </div>
        ) : (
          <DatabaseBody
            schema={schema}
            view={{ ...view, groupBy }}
            groups={groups}
            getId={(task) => task.id}
            onOpen={(task) => navigate({ task: task.id })}
            renderCard={(task, visible) => (
              <TaskCard
                task={task}
                visible={visible}
                schema={schema}
                today={board.today}
                onOpen={() => navigate({ task: task.id })}
              />
            )}
            renderValue={(task, key) => (
              <TaskPropertyValue task={task} propertyKey={key} schema={schema} today={board.today} />
            )}
            renderLeading={(task) => <span className={`board-stage-dot board-stage-${task.stage}`} />}
            renderColumnMarker={
              groupBy === 'stage'
                ? (group: RecordGroup<BoardTask>) => {
                    const stage = stageFromLabel(group.key);
                    return stage ? <span className={`board-stage-dot board-stage-${stage}`} /> : null;
                  }
                : undefined
            }
            onMoveToGroup={
              canDrag
                ? (task, groupKey) => {
                    const fields = fieldsForGroup(groupBy, groupKey);
                    if (fields) void board.updateTask(task.id, fields).catch(() => undefined);
                  }
                : undefined
            }
            renderColumnFooter={
              canCreate && groupBy === 'stage'
                ? (group) => {
                    const stage = stageFromLabel(group.key);
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
          onUpdate={(fields) => board.updateTask(openTask.id, fields)}
          onArchive={(archived) => board.setArchived(openTask.id, archived)}
          onDelete={() => handleDelete(openTask)}
          onClose={() => navigate({ task: null })}
        />
      )}
    </div>
  );
}
