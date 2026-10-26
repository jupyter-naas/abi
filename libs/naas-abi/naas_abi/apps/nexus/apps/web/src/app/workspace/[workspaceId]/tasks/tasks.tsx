'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { CalendarDays, Columns3, Flag, LayoutGrid, Plus, SquareKanban, Table2, Tag, UserRound, X } from 'lucide-react';
import { Header } from '@/components/shell/header';
import { useAuthStore } from '@/stores/auth';
import { usePublishFeatureResource } from '@/stores/feature-pane';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { useWorkspaceStore } from '@/stores/workspace';
import { useConfirm } from '@/components/ui/dialogs';
import { ViewBar, type ViewTypeDef } from '@/components/database-view/view-bar';
import { DatabaseBody } from '@/components/database-view/views';
import { useDatabaseViews } from '@/components/database-view/use-database-views';
import type { RecordGroup } from '@/components/database-view/model';
import {
  TASK_SCOPES,
  DONE_STAGE,
  INBOX_STAGE,
  NO_LABEL,
  NO_PRIORITY,
  SCOPE_LABELS,
  UNASSIGNED,
  tasksPath,
  tasksSettingsPath,
  choiceColor,
  choiceFromLabel,
  choiceLabel,
  formatWeekRange,
  parseScope,
  toIsoDate,
  type TasksScope,
  type TasksSettings,
  type Task,
  type TaskFields,
} from '@/lib/tasks';
import {
  BACKLOG_VIEWS,
  INBOX_VIEWS,
  ITERATION_VIEWS,
  TASK_VIEW_TYPE_LABELS,
  createTaskSchema,
  type TaskPropertyKey,
  type TaskViewType,
} from './lib/task-schema';
import { useTasks } from './lib/use-tasks';
import { IterationBar } from './components/iteration-bar';
import { ScopeTabs } from './components/scope-tabs';
import { TasksMenuBar } from './components/tasks-menu-bar';
import { TaskCard, TaskPropertyValue } from './components/task-card';
import { TaskDrawer } from './components/task-drawer';
import { TaskCreateDialog, type TaskCreateDefaults } from './components/task-create-dialog';
import './tasks.css';

const VIEW_TYPES: ViewTypeDef<TaskViewType>[] = [
  { type: 'board', label: TASK_VIEW_TYPE_LABELS.board, icon: Columns3 },
  { type: 'table', label: TASK_VIEW_TYPE_LABELS.table, icon: Table2 },
  { type: 'gallery', label: TASK_VIEW_TYPE_LABELS.gallery, icon: LayoutGrid },
  { type: 'calendar', label: TASK_VIEW_TYPE_LABELS.calendar, icon: CalendarDays },
];

/** Groupings whose columns a card can be dragged between. */
const DRAGGABLE_GROUPS: TaskPropertyKey[] = ['stage', 'priority'];
/** Scopes backed by an iteration, in the order the Iteration dropdown offers them. */
const ITERATION_SCOPES = ['next', 'current', 'last'] as const;

/** What dropping a card on a board column changes, per grouping property. */
function fieldsForGroup(
  settings: TasksSettings,
  groupBy: TaskPropertyKey | null,
  groupKey: string,
): TaskFields | null {
  const empty = groupKey === '__empty__';
  if (groupBy === 'stage') {
    const stage = choiceFromLabel(settings.stages, groupKey);
    return stage ? { stage } : null;
  }
  if (groupBy === 'priority') return { priority: empty ? null : choiceFromLabel(settings.priorities, groupKey) };
  return null;
}

/** The viewer's tab order, per workspace (a browser convenience, not shared). */
function useTabOrder(workspaceId: string) {
  // v2: the default order changed (Inbox, Backlog, Last, Current, Next); older saved orders are dropped.
  const key = `nexus.tasks.tab-order.v2.${workspaceId}`;
  const [order, setOrder] = useState<TasksScope[]>(TASK_SCOPES);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(key) ?? 'null') as unknown;
      if (Array.isArray(saved)) {
        const known = saved.filter((s): s is TasksScope => TASK_SCOPES.includes(s as TasksScope));
        setOrder([...new Set([...known, ...TASK_SCOPES])]);
        return;
      }
    } catch {
      // Unavailable or corrupt storage: the default order.
    }
    setOrder(TASK_SCOPES);
  }, [key]);
  const save = useCallback(
    (next: TasksScope[]) => {
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

/** Set once the viewer closes the chat pane on Tasks: it stays closed for the session. */
const PANE_DISMISSED_KEY = 'nexus.tasks.pane-dismissed';

/**
 * Opens the chat pane (bound to the Tasks agent) when Tasks opens, on wide
 * screens, until the viewer closes it on Tasks once in this browser session.
 */
function useTasksAgentPane() {
  const isMobile = useIsMobile();
  useEffect(() => {
    if (isMobile) return;
    let dismissed = false;
    try {
      dismissed = sessionStorage.getItem(PANE_DISMISSED_KEY) === '1';
    } catch {
      // Unavailable storage: open it, as on a first visit.
    }
    if (!dismissed) useWorkspaceStore.getState().setContextPanelOpen(true);
    return useWorkspaceStore.subscribe((state, previous) => {
      if (previous.contextPanelOpen && !state.contextPanelOpen) {
        try {
          sessionStorage.setItem(PANE_DISMISSED_KEY, '1');
        } catch {
          // The pane then reopens on the next visit.
        }
      }
    });
  }, [isMobile]);
}

/** Local calendar day of a UTC timestamp from the API. */
function createdDay(timestamp: string): string {
  return toIsoDate(new Date(timestamp.endsWith('Z') ? timestamp : `${timestamp}Z`));
}

export default function TasksPage() {
  const params = useParams();
  const workspaceId = params.workspaceId as string;
  const searchParams = useSearchParams();
  const router = useRouter();
  const { confirm, dialog: confirmDialog } = useConfirm();

  const scope = parseScope(searchParams?.get('view'));
  const openTaskId = searchParams?.get('task') ?? null;
  const isIteration = scope === 'current' || scope === 'last' || scope === 'next';
  const [showArchived, setShowArchived] = useState(false);
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState<{ text: string; scope?: TasksScope } | null>(null);
  const [creating, setCreating] = useState<TaskCreateDefaults | null>(null);

  const store = useTasks(workspaceId, scope, showArchived);
  const [tabOrder, setTabOrder] = useTabOrder(workspaceId);

  const navigate = useCallback(
    (next: { view?: TasksScope; task?: string | null }) => {
      router.replace(
        tasksPath(workspaceId, {
          view: next.view ?? scope,
          task: next.task === null ? undefined : next.task ?? openTaskId ?? undefined,
        }),
      );
    },
    [router, workspaceId, scope, openTaskId],
  );

  const iterationById = useMemo(() => new Map(store.iterations.map((i) => [i.id, i])), [store.iterations]);
  const iterationLabel = useCallback(
    (iterationId: string) => {
      const iteration = iterationById.get(iterationId);
      if (!iteration) return 'Another iteration';
      const range = formatWeekRange(iteration.start_date, iteration.end_date);
      const scope = ITERATION_SCOPES.find((target) => store.scopes[target]?.id === iteration.id);
      return scope ? `${range} (${scope})` : range;
    },
    [iterationById, store.scopes],
  );
  /** Last / current / next iterations not created yet: still offered when moving a task. */
  const pendingScopes = useMemo(
    () => ITERATION_SCOPES.filter((target) => !store.scopes[target] && (target === 'current' || store.scopes.current)),
    [store.scopes],
  );

  const { settings } = store;
  const workspaces = useWorkspaceStore((s) => s.workspaces);
  const currentUserId = useAuthStore((s) => s.user?.id ?? null);
  const workspaceName = useCallback(
    (id: string) => workspaces.find((w) => w.id === id)?.name ?? id,
    [workspaces],
  );
  const schema = useMemo(
    () => createTaskSchema({ memberName: store.memberName, workspaceName, iterationLabel, settings }),
    [store.memberName, workspaceName, iterationLabel, settings],
  );
  const iterationViews = useDatabaseViews(workspaceId, ITERATION_VIEWS);
  const inboxViews = useDatabaseViews(workspaceId, INBOX_VIEWS);
  const backlogViews = useDatabaseViews(workspaceId, BACKLOG_VIEWS);
  const viewsFor = (target: TasksScope) =>
    target === 'inbox' ? inboxViews : target === 'backlog' ? backlogViews : iterationViews;
  const views = viewsFor(scope);
  const view = views.activeView;
  const groupBy = view.type === 'board' ? view.groupBy ?? 'stage' : view.groupBy;

  const groups = useMemo(() => {
    const rows = schema.applySort(
      schema.applySearch(schema.applyFilters(store.tasks, view.filters), search),
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
  }, [schema, store.tasks, view.filters, view.sort, search, groupBy, isIteration, settings.stages]);
  const visibleCount = useMemo(
    () => new Set(groups.flatMap((g) => g.records.map((t) => t.id))).size,
    [groups],
  );

  const labels = useMemo(
    () => Array.from(new Set(store.allTasks.flatMap((t) => t.labels))).sort(),
    [store.allTasks],
  );

  const openTask = store.allTasks.find((t) => t.id === openTaskId) ?? null;

  useTasksAgentPane();
  // The open task rides into the chat pane: the Tasks agent's tools default to it.
  usePublishFeatureResource(
    openTask ? { feature: 'tasks', kind: 'task', id: openTask.id, label: openTask.title } : null,
  );

  /** Opens the New task form, preset for the open tab (and the clicked column's stage). */
  const handleNewTask = (stage?: string) => {
    setCreating({
      stage: stage ?? (scope === 'inbox' ? INBOX_STAGE : settings.default_stage),
      // The tab's iteration may not exist yet: the form then names it and it is created on save.
      iterationId: isIteration ? store.iteration?.id : null,
    });
  };

  const handleCreate = async (fields: TaskFields & { title: string }) => {
    await store.createTask(fields);
  };

  // The sidebar's "New task" opens the Tasks page with ?new=1.
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
    router.replace(tasksPath(workspaceId, { view: scope, task: openTaskId ?? undefined }));
    handleNewTaskRef.current();
  }, [newRequested, router, workspaceId, scope, openTaskId]);

  const handleDropOnScope = async (taskId: string, target: TasksScope) => {
    const task = store.allTasks.find((t) => t.id === taskId);
    if (!task) return;
    try {
      if (await store.moveToScope(task, target)) {
        setNotice({ text: `Moved "${task.title}" to ${SCOPE_LABELS[target]}.`, scope: target });
      }
    } catch {
      // Shown in the error banner.
    }
  };

  const handleCarryOver = async () => {
    try {
      const result = await store.carryOver();
      if (!result) return;
      const target: TasksScope = scope === 'last' ? 'current' : 'next';
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

  const handleDelete = async (task: Task) => {
    const ok = await confirm({
      title: 'Delete task?',
      description: `"${task.title}" and its comments and history are deleted for everyone. Archive it instead to keep it recoverable.`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    try {
      await store.deleteTask(task.id);
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
      names: store.filters.assignees.map((id) => (id === UNASSIGNED ? 'Unassigned' : store.memberName(id))),
    },
    {
      kind: 'priorities' as const,
      icon: Flag,
      plural: 'priorities',
      names: store.filters.priorities.map((key) =>
        key === NO_PRIORITY ? 'No priority' : choiceLabel(settings.priorities, key),
      ),
    },
    {
      kind: 'labels' as const,
      icon: Tag,
      plural: 'labels',
      names: store.filters.labels.map((label) => (label === NO_LABEL ? 'No label' : label)),
    },
  ].filter((chip) => chip.names.length > 0);

  return (
    <div className="tasks-page">
      <Header
        title="Tasks"
        subtitle="Project tasks in weekly iterations"
        nav={
          <TasksMenuBar
            onNewTask={() => handleNewTask()}
            onSettings={() => router.push(tasksSettingsPath(workspaceId))}
          />
        }
      />
      {confirmDialog}

      {store.error && (
        <div className="tasks-error" role="alert">
          <span>{store.error}</span>
          <button type="button" className="tasks-error-dismiss" title="Dismiss" onClick={store.clearError}>
            <X size={12} />
          </button>
        </div>
      )}
      {notice && (
        <div className="tasks-notice" role="status">
          <span>{notice.text}</span>
          <span className="tasks-notice-actions">
            {notice.scope && notice.scope !== scope && (
              <button
                type="button"
                className="tasks-notice-link"
                onClick={() => {
                  setNotice(null);
                  navigate({ view: notice.scope, task: null });
                }}
              >
                Open {SCOPE_LABELS[notice.scope].toLowerCase()}
              </button>
            )}
            <button type="button" className="tasks-error-dismiss" title="Dismiss" onClick={() => setNotice(null)}>
              <X size={12} />
            </button>
          </span>
        </div>
      )}

      <IterationBar
        scope={scope}
        day={store.day}
        iteration={store.iteration}
        showArchived={showArchived}
        canCarryOver={store.tasks.some((t) => t.stage !== DONE_STAGE && !t.archived)}
        onToggleArchived={() => setShowArchived((v) => !v)}
        onCarryOver={() => void handleCarryOver()}
      />

      <ViewBar
        api={views}
        schema={schema}
        viewTypes={VIEW_TYPES}
        records={store.tasks}
        search={search}
        onSearchChange={setSearch}
        defaultFilterProperty="labels"
        groupedTypes={['board']}
        defaultGroupBy="stage"
        iconOnly
        singleRow
        tabs={
          <ScopeTabs
            order={tabOrder}
            onReorder={setTabOrder}
            active={scope}
            counts={store.counts}
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
                className="tasks-filter-chip"
                title={`Set from the Board dashboard in the sidebar: ${names.join(', ')}`}
              >
                <Icon size={12} />
                <span className="tasks-filter-chip-label">
                  {names.length === 1 ? names[0] : `${names.length} ${plural}`}
                </span>
                <button
                  type="button"
                  className="tasks-filter-chip-clear"
                  title={`Show every ${plural === 'priorities' ? 'priority' : plural.slice(0, -1)}`}
                  onClick={() => store.clearFilter(kind)}
                >
                  <X size={11} />
                </button>
              </span>
            ))}
          </>
        }
      />

      <div className="tasks-page-scroll">
        {store.loading ? (
          <div className="tasks-empty">
            <SquareKanban size={18} className="animate-pulse" /> Loading tasks…
          </div>
        ) : (view.type === 'table' || view.type === 'gallery') && visibleCount === 0 ? (
          <div className="tasks-empty">
            <p className="tasks-empty-title">{store.tasks.length ? 'No task matches' : 'No tasks yet'}</p>
            <p>
              {store.tasks.length
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
                    onMoveToDate: (task, day) => void store.updateTask(task.id, { due_date: day }).catch(() => undefined),
                  }
            }
            renderCard={(task, visible) => (
              <TaskCard
                task={task}
                visible={visible}
                schema={schema}
                priorities={settings.priorities}
                today={store.today}
                onOpen={() => navigate({ task: task.id })}
              />
            )}
            renderValue={(task, key) => (
              <TaskPropertyValue
                task={task}
                propertyKey={key}
                schema={schema}
                priorities={settings.priorities}
                today={store.today}
              />
            )}
            renderLeading={(task) => (
              <span className={`tasks-stage-dot tasks-dot-${choiceColor(settings.stages, task.stage)}`} />
            )}
            renderColumnMarker={
              groupBy === 'stage'
                ? (group: RecordGroup<Task>) => {
                    const stage = choiceFromLabel(settings.stages, group.key);
                    return stage ? (
                      <span className={`tasks-stage-dot tasks-dot-${choiceColor(settings.stages, stage)}`} />
                    ) : null;
                  }
                : undefined
            }
            onMoveToGroup={
              canDrag
                ? (task, groupKey) => {
                    const fields = fieldsForGroup(settings, groupBy, groupKey);
                    if (fields) void store.updateTask(task.id, fields).catch(() => undefined);
                  }
                : undefined
            }
            renderColumnFooter={
              isIteration && groupBy === 'stage'
                ? (group) => {
                    const stage = choiceFromLabel(settings.stages, group.key);
                    return stage ? (
                      <button type="button" className="tasks-column-add" onClick={() => handleNewTask(stage)}>
                        <Plus size={12} /> New task
                      </button>
                    ) : null;
                  }
                : undefined
            }
          />
        )}
      </div>

      {creating && (
        <TaskCreateDialog
          defaults={creating}
          scopeIterationLabel={isIteration && !store.iteration ? SCOPE_LABELS[scope] : null}
          iterations={store.iterations}
          iterationLabel={iterationLabel}
          members={store.members}
          memberName={store.memberName}
          labels={labels}
          settings={settings}
          onCreate={handleCreate}
          onClose={() => setCreating(null)}
        />
      )}

      {openTask && (
        <TaskDrawer
          key={openTask.id}
          workspaceId={workspaceId}
          task={openTask}
          iterations={store.iterations}
          iterationLabel={iterationLabel}
          pendingScopes={pendingScopes}
          resolveScopeIteration={store.iterationIdFor}
          members={store.members}
          memberName={store.memberName}
          workspaceName={workspaceName}
          labels={labels}
          settings={settings}
          onUpdate={(fields) => store.updateTask(openTask.id, fields)}
          onArchive={(archived) => store.setArchived(openTask.id, archived)}
          onDelete={() => handleDelete(openTask)}
          onClose={() => navigate({ task: null })}
          currentUserId={currentUserId}
          canModerate={settings.can_edit}
          confirmRemoveComment={(comment) =>
            confirm({
              title: 'Remove comment?',
              description: `"${comment.body.length > 80 ? `${comment.body.slice(0, 79)}…` : comment.body}" and its replies are removed for everyone.`,
              confirmLabel: 'Remove',
            })
          }
          onFeedChange={() => void store.refreshFeed()}
        />
      )}
    </div>
  );
}
