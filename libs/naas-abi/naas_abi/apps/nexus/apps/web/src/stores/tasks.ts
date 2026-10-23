'use client';

import { create } from 'zustand';
import {
  DEFAULT_TASKS_SETTINGS,
  NO_FILTERS,
  tasksApi,
  iterationContaining,
  toIsoDate,
  type TaskIteration,
  type TasksFilterKind,
  type TasksFilters,
  type TasksSettings,
  type TasksMember,
  type Task,
  type TaskFields,
} from '@/lib/tasks';

/**
 * Tasks data of the current workspace, shared by the Tasks page, its settings
 * page and the sidebar dashboard: settings, iterations, members, every task
 * (archived included) and the sidebar filters (assignees, priorities, labels)
 * that both apply.
 *
 * Task edits apply locally first and roll back when the API refuses them;
 * last write wins between users. The current iteration is created on first
 * load; the last and next ones only when a task or a goal needs them.
 */

interface TasksState {
  workspaceId: string | null;
  settings: TasksSettings;
  iterations: TaskIteration[];
  members: TasksMember[];
  tasks: Task[];
  /** False until the workspace's first load finishes. */
  loaded: boolean;
  error: string | null;
  /** Assignee, priority and label filters; empty lists filter nothing. */
  filters: TasksFilters;

  /** Loads the workspace; ``force`` refreshes data already loaded, in place. */
  load: (workspaceId: string, options?: { force?: boolean }) => Promise<void>;
  toggleFilter: (kind: TasksFilterKind, value: string) => void;
  clearFilter: (kind: TasksFilterKind) => void;
  clearError: () => void;
  saveSettings: (settings: Parameters<typeof tasksApi.saveSettings>[1]) => Promise<TasksSettings>;
  /** The iteration ``day`` falls in, created when missing. */
  ensureIteration: (day: string) => Promise<TaskIteration>;
  setGoal: (day: string, goal: string) => Promise<void>;
  /** Moves the iteration's unfinished tasks to the week after it. */
  carryOver: (iterationId: string) => Promise<{ week: string; moved: number }>;
  createTask: (fields: TaskFields & { title: string }) => Promise<Task>;
  updateTask: (taskId: string, fields: TaskFields) => Promise<Task>;
  setArchived: (taskId: string, archived: boolean) => Promise<Task>;
  deleteTask: (taskId: string) => Promise<void>;
}

const byStart = (a: TaskIteration, b: TaskIteration) => a.start_date.localeCompare(b.start_date);

let inflight: { workspaceId: string; promise: Promise<void> } | null = null;

export const useTasksStore = create<TasksState>()((set, get) => {
  const workspace = (): string => {
    const id = get().workspaceId;
    if (!id) throw new Error('No workspace selected');
    return id;
  };

  const fail = (e: unknown): never => {
    set({ error: (e as Error).message });
    throw e;
  };

  const upsertIteration = (next: TaskIteration) =>
    set((s) => ({ iterations: [...s.iterations.filter((i) => i.id !== next.id), next].sort(byStart) }));

  /** Only tasks of the workspace on screen enter the store (a reply can land after a switch). */
  const replaceTask = (next: Task) =>
    set((s) =>
      next.workspace_id === s.workspaceId ? { tasks: [next, ...s.tasks.filter((t) => t.id !== next.id)] } : {},
    );

  return {
    workspaceId: null,
    settings: DEFAULT_TASKS_SETTINGS,
    iterations: [],
    members: [],
    tasks: [],
    loaded: false,
    error: null,
    filters: NO_FILTERS,

    load: async (workspaceId, options) => {
      // A load already running for this workspace is fresh enough, forced or not.
      if (inflight?.workspaceId === workspaceId) return inflight.promise;
      const switching = get().workspaceId !== workspaceId;
      if (!switching && !options?.force && get().loaded) return;
      if (switching) {
        set({
          workspaceId,
          settings: DEFAULT_TASKS_SETTINGS,
          iterations: [],
          members: [],
          tasks: [],
          loaded: false,
          error: null,
          filters: NO_FILTERS,
        });
      }
      const promise = (async () => {
        try {
          const today = toIsoDate(new Date());
          const [settings, iterations, members, tasks] = await Promise.all([
            tasksApi.getSettings(workspaceId),
            tasksApi.listIterations(workspaceId),
            tasksApi.listMembers(workspaceId).catch(() => [] as TasksMember[]),
            tasksApi.listAllTasks(workspaceId, true),
          ]);
          let all = iterations;
          if (!iterationContaining(iterations, today)) {
            all = [...iterations, await tasksApi.ensureIteration(workspaceId, today)];
          }
          if (get().workspaceId !== workspaceId) return;
          set({ settings, iterations: all.sort(byStart), members, tasks, loaded: true, error: null });
        } catch (e) {
          if (get().workspaceId === workspaceId) set({ error: (e as Error).message, loaded: true });
        } finally {
          if (inflight?.workspaceId === workspaceId) inflight = null;
        }
      })();
      inflight = { workspaceId, promise };
      return promise;
    },

    toggleFilter: (kind, value) =>
      set((s) => {
        const current = s.filters[kind];
        const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
        return { filters: { ...s.filters, [kind]: next } };
      }),
    clearFilter: (kind) => set((s) => ({ filters: { ...s.filters, [kind]: [] } })),
    clearError: () => set({ error: null }),

    saveSettings: async (next) => {
      try {
        const saved = await tasksApi.saveSettings(workspace(), next, toIsoDate(new Date()));
        set({ settings: saved, error: null });
        return saved;
      } catch (e) {
        return fail(e);
      }
    },

    ensureIteration: async (day) => {
      const existing = iterationContaining(get().iterations, day);
      if (existing) return existing;
      try {
        const created = await tasksApi.ensureIteration(workspace(), day);
        upsertIteration(created);
        return created;
      } catch (e) {
        return fail(e);
      }
    },

    setGoal: async (day, goal) => {
      const iteration = await get().ensureIteration(day);
      try {
        upsertIteration(await tasksApi.updateGoal(workspace(), iteration.id, goal));
      } catch (e) {
        fail(e);
      }
    },

    carryOver: async (iterationId) => {
      try {
        const result = await tasksApi.carryOver(workspace(), iterationId);
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
        const created = await tasksApi.createTask(workspace(), fields);
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
        const updated = await tasksApi.updateTask(workspace(), taskId, fields);
        set((s) => ({
          tasks: s.tasks.map((t) => (t.id === taskId && updated.workspace_id === s.workspaceId ? updated : t)),
        }));
        return updated;
      } catch (e) {
        if (before) set((s) => ({ tasks: s.tasks.map((t) => (t.id === taskId ? before : t)) }));
        return fail(e);
      }
    },

    setArchived: async (taskId, archived) => {
      try {
        const updated = archived
          ? await tasksApi.archiveTask(workspace(), taskId)
          : await tasksApi.restoreTask(workspace(), taskId);
        set((s) => ({ tasks: s.tasks.map((t) => (t.id === taskId ? updated : t)) }));
        return updated;
      } catch (e) {
        return fail(e);
      }
    },

    deleteTask: async (taskId) => {
      try {
        await tasksApi.deleteTask(workspace(), taskId);
        set((s) => ({ tasks: s.tasks.filter((t) => t.id !== taskId) }));
      } catch (e) {
        fail(e);
      }
    },
  };
});
