'use client';

import { useCallback, useEffect, useMemo } from 'react';
import {
  BOARD_SCOPES,
  INBOX_STAGE,
  fieldsForScope,
  matchesFilters,
  scopeDay,
  scopeIterations,
  taskInScope,
  toIsoDate,
  type BoardScope,
  type BoardTask,
  type TaskFields,
} from '@/lib/board';
import { useBoardStore } from '@/stores/board';

/**
 * The board page's view of the shared board store: the tasks of one scope,
 * after the sidebar filters, plus the scope-aware actions (creating a task in
 * the scope, moving a task to another scope).
 */
export function useBoard(workspaceId: string, scope: BoardScope, showArchived: boolean) {
  const today = useMemo(() => toIsoDate(new Date()), []);

  const store = useBoardStore();
  const { load, settings, iterations, members, tasks, filters, ensureIteration } = store;

  // Fresh data on every visit; the sidebar may have loaded it earlier.
  useEffect(() => {
    if (workspaceId) void load(workspaceId, { force: true });
  }, [workspaceId, load]);

  const scopes = useMemo(() => scopeIterations(iterations, today), [iterations, today]);
  const scopeIterationId = useCallback(
    (target: BoardScope) =>
      target === 'inbox' || target === 'backlog' ? null : scopes[target]?.id ?? null,
    [scopes],
  );

  /** A day inside the scope (null for Inbox and Backlog), even before its iteration exists. */
  const day = scopeDay(scope, scopes.current, today);
  const iteration = scope === 'inbox' || scope === 'backlog' ? null : scopes[scope];

  /** Tasks the filters let through, whatever their scope. */
  const filtered = useMemo(
    () => tasks.filter((t) => (showArchived || !t.archived) && matchesFilters(t, filters)),
    [tasks, showArchived, filters],
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

  /** The iteration a scope needs for a write, created when it has none yet. */
  const iterationIdFor = useCallback(
    async (target: BoardScope) => {
      const targetDay = scopeDay(target, scopes.current, today);
      return targetDay ? (await ensureIteration(targetDay)).id : null;
    },
    [ensureIteration, scopes, today],
  );

  /** New task in this scope: Inbox triage, the backlog, or an iteration column. */
  const createTask = useCallback(
    async (fields: TaskFields & { title: string }) => {
      if (scope === 'inbox') return store.createTask({ ...fields, stage: INBOX_STAGE, iteration_id: null });
      const iterationId = await iterationIdFor(scope);
      return store.createTask({ stage: settings.default_stage, ...fields, iteration_id: iterationId });
    },
    [scope, iterationIdFor, store, settings.default_stage],
  );

  /** Drop on a scope tab. Resolves false when the task was already there. */
  const moveToScope = useCallback(
    async (task: BoardTask, target: BoardScope) => {
      const stage = settings.default_stage;
      if (fieldsForScope(task, target, scopeIterationId(target), stage) === null) return false;
      const fields = fieldsForScope(task, target, await iterationIdFor(target), stage);
      if (fields) await store.updateTask(task.id, fields);
      return !!fields;
    },
    [scopeIterationId, iterationIdFor, store, settings.default_stage],
  );

  return {
    today,
    settings,
    saveSettings: store.saveSettings,
    day,
    iteration,
    currentIteration: scopes.current,
    iterations,
    members,
    memberName,
    allTasks: tasks,
    tasks: scopeTasks,
    counts,
    filters,
    clearFilter: store.clearFilter,
    loading: !store.loaded,
    error: store.error,
    clearError: store.clearError,
    setGoal: (goal: string) => (day ? store.setGoal(day, goal) : Promise.resolve()),
    carryOver: () => (iteration ? store.carryOver(iteration.id) : Promise.resolve(null)),
    createTask,
    moveToScope,
    updateTask: store.updateTask,
    setArchived: store.setArchived,
    deleteTask: store.deleteTask,
  };
}

export type BoardApi = ReturnType<typeof useBoard>;
