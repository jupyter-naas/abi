'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  addWeeks,
  boardApi,
  toIsoDate,
  weekStart,
  type BoardIteration,
  type BoardMember,
  type BoardTask,
  type TaskFields,
} from '@/lib/board';

export type BoardScope = { kind: 'week'; week: string } | { kind: 'backlog' };

/**
 * Board data for one scope (a week or the backlog): iterations, tasks and the
 * members who can be assigned. Task edits apply locally first and roll back
 * when the API refuses them; last write wins between users.
 *
 * The current week's iteration is created on first open. Any other week is
 * only created when the user asks (`createIteration`).
 */
export function useBoard(workspaceId: string, scope: BoardScope, showArchived: boolean) {
  const today = useMemo(() => toIsoDate(new Date()), []);
  const currentWeek = weekStart(today);

  const [iterations, setIterations] = useState<BoardIteration[]>([]);
  const [iterationsLoaded, setIterationsLoaded] = useState(false);
  const [members, setMembers] = useState<BoardMember[]>([]);
  const [tasks, setTasks] = useState<BoardTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const tasksRef = useRef<BoardTask[]>([]);
  tasksRef.current = tasks;

  const week = scope.kind === 'week' ? weekStart(scope.week) : null;
  const iteration = useMemo(
    () => (week ? iterations.find((i) => i.start_date === week) ?? null : null),
    [iterations, week],
  );
  const missingIteration = scope.kind === 'week' && iterationsLoaded && !iteration;

  const upsertIteration = useCallback((next: BoardIteration) => {
    setIterations((prev) =>
      [...prev.filter((i) => i.id !== next.id), next].sort((a, b) => a.start_date.localeCompare(b.start_date)),
    );
  }, []);

  // Iterations and members, once per workspace. The current week always exists.
  useEffect(() => {
    if (!workspaceId) return;
    let cancelled = false;
    setIterationsLoaded(false);
    setError(null);
    (async () => {
      try {
        const [listed, people] = await Promise.all([
          boardApi.listIterations(workspaceId),
          boardApi.listMembers(workspaceId).catch(() => [] as BoardMember[]),
        ]);
        let all = listed;
        if (!listed.some((i) => i.start_date === currentWeek)) {
          all = [...listed, await boardApi.ensureIteration(workspaceId, today)];
        }
        if (cancelled) return;
        setIterations(all.sort((a, b) => a.start_date.localeCompare(b.start_date)));
        setMembers(people);
        setIterationsLoaded(true);
      } catch (e) {
        if (!cancelled) {
          setError((e as Error).message);
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, today, currentWeek]);

  // Tasks of the scope.
  const iterationId = iteration?.id ?? null;
  const reloadTasks = useCallback(async () => {
    if (!workspaceId || !iterationsLoaded) return;
    if (scope.kind === 'week' && !iterationId) {
      setTasks([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const listed = await boardApi.listTasks(
        workspaceId,
        scope.kind === 'backlog' ? { backlog: true } : { iterationId: iterationId as string },
        showArchived,
      );
      setTasks(listed);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, iterationsLoaded, scope.kind, iterationId, showArchived]);

  useEffect(() => {
    void reloadTasks();
  }, [reloadTasks]);

  const memberById = useMemo(() => new Map(members.map((m) => [m.user_id, m])), [members]);
  const memberName = useCallback(
    (userId: string) => {
      const member = memberById.get(userId);
      return member?.name || member?.email || 'Former member';
    },
    [memberById],
  );

  // -- Mutations ----------------------------------------------------------------

  const fail = (e: unknown) => {
    setError((e as Error).message);
    throw e;
  };

  /** Keep a task in the list only while it still belongs to the scope. */
  const inScope = useCallback(
    (task: BoardTask) =>
      (showArchived || !task.archived) &&
      (scope.kind === 'backlog' ? task.iteration_id === null : task.iteration_id === iterationId),
    [showArchived, scope.kind, iterationId],
  );

  const replaceTask = useCallback(
    (next: BoardTask) => {
      setTasks((prev) => {
        const without = prev.filter((t) => t.id !== next.id);
        return inScope(next) ? [...without, next] : without;
      });
    },
    [inScope],
  );

  const createIteration = useCallback(async () => {
    if (!week) return;
    try {
      upsertIteration(await boardApi.ensureIteration(workspaceId, week));
    } catch (e) {
      fail(e);
    }
  }, [workspaceId, week, upsertIteration]);

  const setGoal = useCallback(
    async (goal: string) => {
      if (!iteration) return;
      try {
        upsertIteration(await boardApi.updateGoal(workspaceId, iteration.id, goal));
      } catch (e) {
        fail(e);
      }
    },
    [workspaceId, iteration, upsertIteration],
  );

  /** Moves unfinished tasks to next week. Returns the next week's Monday. */
  const carryOver = useCallback(async (): Promise<{ week: string; moved: number } | null> => {
    if (!iteration) return null;
    try {
      const result = await boardApi.carryOver(workspaceId, iteration.id);
      upsertIteration(result.iteration);
      const movedIds = new Set(result.moved.map((t) => t.id));
      setTasks((prev) => prev.filter((t) => !movedIds.has(t.id)));
      return { week: result.iteration.start_date, moved: result.moved.length };
    } catch (e) {
      return fail(e);
    }
  }, [workspaceId, iteration, upsertIteration]);

  const createTask = useCallback(
    async (fields: TaskFields & { title: string }) => {
      try {
        const created = await boardApi.createTask(workspaceId, {
          iteration_id: scope.kind === 'week' ? iterationId : null,
          ...fields,
        });
        replaceTask(created);
        return created;
      } catch (e) {
        return fail(e);
      }
    },
    [workspaceId, scope.kind, iterationId, replaceTask],
  );

  const updateTask = useCallback(
    async (taskId: string, fields: TaskFields) => {
      const before = tasksRef.current.find((t) => t.id === taskId);
      if (before) setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, ...fields } : t)));
      try {
        const updated = await boardApi.updateTask(workspaceId, taskId, fields);
        replaceTask(updated);
        return updated;
      } catch (e) {
        if (before) setTasks((prev) => prev.map((t) => (t.id === taskId ? before : t)));
        return fail(e);
      }
    },
    [workspaceId, replaceTask],
  );

  const setArchived = useCallback(
    async (taskId: string, archived: boolean) => {
      try {
        const updated = archived
          ? await boardApi.archiveTask(workspaceId, taskId)
          : await boardApi.restoreTask(workspaceId, taskId);
        replaceTask(updated);
        return updated;
      } catch (e) {
        return fail(e);
      }
    },
    [workspaceId, replaceTask],
  );

  const deleteTask = useCallback(
    async (taskId: string) => {
      try {
        await boardApi.deleteTask(workspaceId, taskId);
        setTasks((prev) => prev.filter((t) => t.id !== taskId));
      } catch (e) {
        fail(e);
      }
    },
    [workspaceId],
  );

  return {
    today,
    currentWeek,
    week,
    previousWeek: week ? addWeeks(week, -1) : null,
    nextWeek: week ? addWeeks(week, 1) : null,
    iterations,
    iteration,
    missingIteration,
    tasks,
    members,
    memberName,
    loading: loading || !iterationsLoaded,
    error,
    clearError: () => setError(null),
    reloadTasks,
    createIteration,
    setGoal,
    carryOver,
    createTask,
    updateTask,
    setArchived,
    deleteTask,
  };
}

export type BoardApi = ReturnType<typeof useBoard>;
