'use client';

import { create } from 'zustand';
import {
  DEFAULT_BOARD_SETTINGS,
  NO_FILTERS,
  boardApi,
  iterationContaining,
  toIsoDate,
  type BoardIteration,
  type BoardFilterKind,
  type BoardFilters,
  type BoardSettings,
  type BoardMember,
  type BoardTask,
  type TaskFields,
} from '@/lib/board';

/**
 * Board data of the current workspace, shared by the board page, its settings
 * page and the sidebar dashboard: settings, iterations, members, every task
 * (archived included) and the sidebar filters (assignees, priorities, labels)
 * that both apply.
 *
 * Task edits apply locally first and roll back when the API refuses them;
 * last write wins between users. The current iteration is created on first
 * load; the last and next ones only when a task or a goal needs them.
 */

interface BoardState {
  workspaceId: string | null;
  settings: BoardSettings;
  iterations: BoardIteration[];
  members: BoardMember[];
  tasks: BoardTask[];
  /** False until the workspace's first load finishes. */
  loaded: boolean;
  error: string | null;
  /** Assignee, priority and label filters; empty lists filter nothing. */
  filters: BoardFilters;

  /** Loads the workspace; ``force`` refreshes data already loaded, in place. */
  load: (workspaceId: string, options?: { force?: boolean }) => Promise<void>;
  toggleFilter: (kind: BoardFilterKind, value: string) => void;
  clearFilter: (kind: BoardFilterKind) => void;
  clearError: () => void;
  saveSettings: (settings: Parameters<typeof boardApi.saveSettings>[1]) => Promise<BoardSettings>;
  /** The iteration ``day`` falls in, created when missing. */
  ensureIteration: (day: string) => Promise<BoardIteration>;
  setGoal: (day: string, goal: string) => Promise<void>;
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

  /** Only tasks of the workspace on screen enter the store (a reply can land after a switch). */
  const replaceTask = (next: BoardTask) =>
    set((s) =>
      next.workspace_id === s.workspaceId ? { tasks: [next, ...s.tasks.filter((t) => t.id !== next.id)] } : {},
    );

  return {
    workspaceId: null,
    settings: DEFAULT_BOARD_SETTINGS,
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
          settings: DEFAULT_BOARD_SETTINGS,
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
            boardApi.getSettings(workspaceId),
            boardApi.listIterations(workspaceId),
            boardApi.listMembers(workspaceId).catch(() => [] as BoardMember[]),
            boardApi.listAllTasks(workspaceId, true),
          ]);
          let all = iterations;
          if (!iterationContaining(iterations, today)) {
            all = [...iterations, await boardApi.ensureIteration(workspaceId, today)];
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
        const saved = await boardApi.saveSettings(workspace(), next, toIsoDate(new Date()));
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
        const created = await boardApi.ensureIteration(workspace(), day);
        upsertIteration(created);
        return created;
      } catch (e) {
        return fail(e);
      }
    },

    setGoal: async (day, goal) => {
      const iteration = await get().ensureIteration(day);
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
