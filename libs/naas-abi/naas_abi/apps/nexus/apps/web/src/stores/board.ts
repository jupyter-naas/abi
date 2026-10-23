'use client';

import { create } from 'zustand';
import {
  boardApi,
  toIsoDate,
  weekStart,
  type BoardIteration,
  type BoardMember,
  type BoardTask,
  type TaskFields,
} from '@/lib/board';

/**
 * Board data of the current workspace, shared by the board page and the
 * sidebar dashboard: iterations, members, every task (archived included) and
 * the assignee filter both apply.
 *
 * Task edits apply locally first and roll back when the API refuses them;
 * last write wins between users. The current week's iteration is created on
 * first load; other weeks only when a task or a goal needs them.
 */

interface BoardState {
  workspaceId: string | null;
  iterations: BoardIteration[];
  members: BoardMember[];
  tasks: BoardTask[];
  /** False until the workspace's first load finishes. */
  loaded: boolean;
  error: string | null;
  /** User ids and/or UNASSIGNED; empty shows everyone. */
  assignees: string[];

  /** Loads the workspace; ``force`` refreshes data already loaded, in place. */
  load: (workspaceId: string, options?: { force?: boolean }) => Promise<void>;
  toggleAssignee: (assignee: string) => void;
  clearAssignees: () => void;
  clearError: () => void;
  /** The iteration of that Monday's week, created when missing. */
  ensureWeek: (week: string) => Promise<BoardIteration>;
  setGoal: (week: string, goal: string) => Promise<void>;
  /** Moves the iteration's unfinished tasks to the week after it. */
  carryOver: (iterationId: string) => Promise<{ week: string; moved: number }>;
  createTask: (fields: TaskFields & { title: string }) => Promise<BoardTask>;
  updateTask: (taskId: string, fields: TaskFields) => Promise<BoardTask>;
  setArchived: (taskId: string, archived: boolean) => Promise<BoardTask>;
  deleteTask: (taskId: string) => Promise<void>;
}

const byStart = (a: BoardIteration, b: BoardIteration) => a.start_date.localeCompare(b.start_date);

let inflight: { workspaceId: string; promise: Promise<void> } | null = null;

export const useBoardStore = create<BoardState>()((set, get) => {
  const workspace = (): string => {
    const id = get().workspaceId;
    if (!id) throw new Error('No workspace selected');
    return id;
  };

  const fail = (e: unknown): never => {
    set({ error: (e as Error).message });
    throw e;
  };

  const upsertIteration = (next: BoardIteration) =>
    set((s) => ({ iterations: [...s.iterations.filter((i) => i.id !== next.id), next].sort(byStart) }));

  const replaceTask = (next: BoardTask) =>
    set((s) => ({ tasks: [next, ...s.tasks.filter((t) => t.id !== next.id)] }));

  return {
    workspaceId: null,
    iterations: [],
    members: [],
    tasks: [],
    loaded: false,
    error: null,
    assignees: [],

    load: async (workspaceId, options) => {
      // A load already running for this workspace is fresh enough, forced or not.
      if (inflight?.workspaceId === workspaceId) return inflight.promise;
      const switching = get().workspaceId !== workspaceId;
      if (!switching && !options?.force && get().loaded) return;
      if (switching) {
        set({ workspaceId, iterations: [], members: [], tasks: [], loaded: false, error: null, assignees: [] });
      }
      const promise = (async () => {
        try {
          const today = toIsoDate(new Date());
          const [iterations, members, tasks] = await Promise.all([
            boardApi.listIterations(workspaceId),
            boardApi.listMembers(workspaceId).catch(() => [] as BoardMember[]),
            boardApi.listAllTasks(workspaceId, true),
          ]);
          let all = iterations;
          if (!iterations.some((i) => i.start_date === weekStart(today))) {
            all = [...iterations, await boardApi.ensureIteration(workspaceId, today)];
          }
          if (get().workspaceId !== workspaceId) return;
          set({ iterations: all.sort(byStart), members, tasks, loaded: true, error: null });
        } catch (e) {
          if (get().workspaceId === workspaceId) set({ error: (e as Error).message, loaded: true });
        } finally {
          if (inflight?.workspaceId === workspaceId) inflight = null;
        }
      })();
      inflight = { workspaceId, promise };
      return promise;
    },

    toggleAssignee: (assignee) =>
      set((s) => ({
        assignees: s.assignees.includes(assignee)
          ? s.assignees.filter((a) => a !== assignee)
          : [...s.assignees, assignee],
      })),
    clearAssignees: () => set({ assignees: [] }),
    clearError: () => set({ error: null }),

    ensureWeek: async (week) => {
      const existing = get().iterations.find((i) => i.start_date === week);
      if (existing) return existing;
      try {
        const created = await boardApi.ensureIteration(workspace(), week);
        upsertIteration(created);
        return created;
      } catch (e) {
        return fail(e);
      }
    },

    setGoal: async (week, goal) => {
      const iteration = await get().ensureWeek(week);
      try {
        upsertIteration(await boardApi.updateGoal(workspace(), iteration.id, goal));
      } catch (e) {
        fail(e);
      }
    },

    carryOver: async (iterationId) => {
      try {
        const result = await boardApi.carryOver(workspace(), iterationId);
        upsertIteration(result.iteration);
        const moved = new Map(result.moved.map((t) => [t.id, t]));
        set((s) => ({ tasks: s.tasks.map((t) => moved.get(t.id) ?? t) }));
        return { week: result.iteration.start_date, moved: result.moved.length };
      } catch (e) {
        return fail(e);
      }
    },

    createTask: async (fields) => {
      try {
        const created = await boardApi.createTask(workspace(), fields);
        replaceTask(created);
        return created;
      } catch (e) {
        return fail(e);
      }
    },

    updateTask: async (taskId, fields) => {
      const before = get().tasks.find((t) => t.id === taskId);
      if (before) set((s) => ({ tasks: s.tasks.map((t) => (t.id === taskId ? { ...t, ...fields } : t)) }));
      try {
        const updated = await boardApi.updateTask(workspace(), taskId, fields);
        set((s) => ({ tasks: s.tasks.map((t) => (t.id === taskId ? updated : t)) }));
        return updated;
      } catch (e) {
        if (before) set((s) => ({ tasks: s.tasks.map((t) => (t.id === taskId ? before : t)) }));
        return fail(e);
      }
    },

    setArchived: async (taskId, archived) => {
      try {
        const updated = archived
          ? await boardApi.archiveTask(workspace(), taskId)
          : await boardApi.restoreTask(workspace(), taskId);
        set((s) => ({ tasks: s.tasks.map((t) => (t.id === taskId ? updated : t)) }));
        return updated;
      } catch (e) {
        return fail(e);
      }
    },

    deleteTask: async (taskId) => {
      try {
        await boardApi.deleteTask(workspace(), taskId);
        set((s) => ({ tasks: s.tasks.filter((t) => t.id !== taskId) }));
      } catch (e) {
        fail(e);
      }
    },
  };
});
