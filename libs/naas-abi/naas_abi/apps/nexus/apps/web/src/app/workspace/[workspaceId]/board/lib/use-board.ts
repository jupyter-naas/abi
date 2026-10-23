'use client';

import { useCallback, useEffect, useMemo } from 'react';
import {
  BOARD_SCOPES,
  fieldsForScope,
  matchesAssignee,
  scopeWeek,
  taskInScope,
  toIsoDate,
  weekStart,
  type BoardScope,
  type BoardTask,
  type TaskFields,
} from '@/lib/board';
import { useBoardStore } from '@/stores/board';

/**
 * The board page's view of the shared board store: the tasks of one scope,
 * after the assignee filter, plus the scope-aware actions (creating a task in
 * the scope, moving a task to another scope).
 */
export function useBoard(workspaceId: string, scope: BoardScope, showArchived: boolean) {
  const today = useMemo(() => toIsoDate(new Date()), []);
  const currentWeek = weekStart(today);

  const store = useBoardStore();
  const { load, iterations, members, tasks, assignees, ensureWeek } = store;

  // Fresh data on every visit; the sidebar may have loaded it earlier.
  useEffect(() => {
    if (workspaceId) void load(workspaceId, { force: true });
  }, [workspaceId, load]);

  const iterationOfWeek = useCallback(
    (week: string | null) => (week ? iterations.find((i) => i.start_date === week) ?? null : null),
    [iterations],
  );
  const scopeIterationId = useCallback(
    (target: BoardScope) => iterationOfWeek(scopeWeek(target, currentWeek))?.id ?? null,
    [iterationOfWeek, currentWeek],
  );

  const week = scopeWeek(scope, currentWeek);
  const iteration = iterationOfWeek(week);

  /** Tasks the filters let through, whatever their scope. */
  const filtered = useMemo(
    () => tasks.filter((t) => (showArchived || !t.archived) && matchesAssignee(t, assignees)),
    [tasks, showArchived, assignees],
  );
  const scopeTasks = useMemo(
    () => filtered.filter((t) => taskInScope(t, scope, iteration?.id ?? null)),
    [filtered, scope, iteration],
  );
  const counts = useMemo(() => {
    const result = {} as Record<BoardScope, number>;
    for (const target of BOARD_SCOPES) {
      const id = scopeIterationId(target);
      result[target] = filtered.filter((t) => !t.archived && taskInScope(t, target, id)).length;
    }
    return result;
  }, [filtered, scopeIterationId]);

  const memberById = useMemo(() => new Map(members.map((m) => [m.user_id, m])), [members]);
  const memberName = useCallback(
    (userId: string) => {
      const member = memberById.get(userId);
      return member?.name || member?.email || 'Former member';
    },
    [memberById],
  );

  /** The iteration a scope needs for a write, created when the week has none. */
  const iterationIdFor = useCallback(
    async (target: BoardScope) => {
      const targetWeek = scopeWeek(target, currentWeek);
      return targetWeek ? (await ensureWeek(targetWeek)).id : null;
    },
    [ensureWeek, currentWeek],
  );

  /** New task in this scope: Inbox triage, the backlog, or an iteration column. */
  const createTask = useCallback(
    async (fields: TaskFields & { title: string }) => {
      if (scope === 'inbox') return store.createTask({ ...fields, stage: 'inbox', iteration_id: null });
      const iterationId = await iterationIdFor(scope);
      return store.createTask({ stage: 'ready', ...fields, iteration_id: iterationId });
    },
    [scope, iterationIdFor, store],
  );

  /** Drop on a scope tab. Resolves false when the task was already there. */
  const moveToScope = useCallback(
    async (task: BoardTask, target: BoardScope) => {
      if (fieldsForScope(task, target, scopeIterationId(target)) === null) return false;
      const fields = fieldsForScope(task, target, await iterationIdFor(target));
      if (fields) await store.updateTask(task.id, fields);
      return !!fields;
    },
    [scopeIterationId, iterationIdFor, store],
  );

  return {
    today,
    currentWeek,
    week,
    iteration,
    iterations,
    members,
    memberName,
    allTasks: tasks,
    tasks: scopeTasks,
    counts,
    assignees,
    clearAssignees: store.clearAssignees,
    loading: !store.loaded,
    error: store.error,
    clearError: store.clearError,
    setGoal: (goal: string) => (week ? store.setGoal(week, goal) : Promise.resolve()),
    carryOver: () => (iteration ? store.carryOver(iteration.id) : Promise.resolve(null)),
    createTask,
    moveToScope,
    updateTask: store.updateTask,
    setArchived: store.setArchived,
    deleteTask: store.deleteTask,
  };
}

export type BoardApi = ReturnType<typeof useBoard>;
