import { describe, expect, it } from 'vitest';
import {
  DEFAULT_TASKS_SETTINGS,
  NO_FILTERS,
  NO_LABEL,
  NO_PRIORITY,
  UNASSIGNED,
  addWeeks,
  tasksPath,
  choiceColor,
  choiceFromLabel,
  choiceLabel,
  fieldsForScope,
  iterationContaining,
  matchesAssignee,
  matchesFilters,
  matchesLabel,
  matchesPriority,
  parseScope,
  scopeDay,
  scopeIterations,
  scopeOfTask,
  taskInScope,
  toIsoDate,
  weekStart,
  type TaskIteration,
  type Task,
} from './tasks';

const task = (overrides: Partial<Task>): Task => ({
  id: 't',
  workspace_id: 'ws',
  title: 'T',
  content: '',
  stage: 'ready',
  iteration_id: null,
  project: '',
  priority: null,
  due_date: null,
  labels: [],
  assignee_ids: [],
  archived: false,
  archived_at: null,
  created_by: null,
  created_at: null,
  updated_by: null,
  updated_at: null,
  ...overrides,
});

describe('weekStart', () => {
  it('returns the Monday of the ISO week for every day of the week', () => {
    for (let day = 19; day <= 25; day += 1) {
      expect(weekStart(`2026-10-${day}`)).toBe('2026-10-19');
    }
  });

  it('crosses month and year boundaries', () => {
    expect(weekStart('2026-11-01')).toBe('2026-10-26');
    expect(weekStart('2027-01-01')).toBe('2026-12-28');
  });
});

describe('addWeeks', () => {
  it('moves by whole weeks, across years', () => {
    expect(addWeeks('2026-10-19', 1)).toBe('2026-10-26');
    expect(addWeeks('2026-10-19', -1)).toBe('2026-10-12');
    expect(addWeeks('2026-12-28', 1)).toBe('2027-01-04');
  });

  it('keeps local days across a DST change', () => {
    // Europe moves clocks back on 2026-10-25: still exactly one calendar week.
    expect(addWeeks('2026-10-19', 2)).toBe('2026-11-02');
  });
});

describe('toIsoDate', () => {
  it('uses the local calendar day, not UTC', () => {
    expect(toIsoDate(new Date(2026, 9, 22, 23, 59))).toBe('2026-10-22');
  });
});

describe('tasksPath', () => {
  it('builds scope and task links; the current iteration is the default', () => {
    expect(tasksPath('ws 1')).toBe('/workspace/ws%201/tasks');
    expect(tasksPath('ws', { view: 'current' })).toBe('/workspace/ws/tasks');
    expect(tasksPath('ws', { view: 'backlog' })).toBe('/workspace/ws/tasks?view=backlog');
    expect(tasksPath('ws', { view: 'next', task: 't1' })).toBe('/workspace/ws/tasks?view=next&task=t1');
    expect(tasksPath('ws', { view: 'inbox', newTask: true })).toBe('/workspace/ws/tasks?view=inbox&new=1');
  });

  it('reads unknown views as the current iteration', () => {
    expect(parseScope('inbox')).toBe('inbox');
    expect(parseScope('week')).toBe('current');
    expect(parseScope(null)).toBe('current');
  });
});

const iteration = (id: string, start_date: string, end_date: string): TaskIteration => ({
  id,
  workspace_id: 'ws',
  start_date,
  end_date,
  iso_week: '',
  goal: '',
  created_by: null,
  created_at: null,
  updated_by: null,
  updated_at: null,
});

describe('scopes', () => {
  const today = '2026-10-22';
  const iterations = [
    iteration('it-0', '2026-10-12', '2026-10-18'),
    iteration('it-1', '2026-10-19', '2026-10-25'),
    // Two-week rhythm after the current week.
    iteration('it-2', '2026-10-26', '2026-11-08'),
  ];

  it('resolves last, current and next from the iteration today falls in', () => {
    const scopes = scopeIterations(iterations, today);
    expect([scopes.last?.id, scopes.current?.id, scopes.next?.id]).toEqual(['it-0', 'it-1', 'it-2']);
    expect(scopeIterations(iterations.slice(1, 2), today).next).toBeNull();
    expect(scopeDay('next', iterations[1], today)).toBe('2026-10-26');
    expect(scopeDay('last', iterations[1], today)).toBe('2026-10-18');
    expect(scopeDay('inbox', iterations[1], today)).toBeNull();
    expect(iterationContaining(iterations, '2026-11-08')?.id).toBe('it-2');
  });

  it('shows Inbox tasks only in Inbox, wherever they are scheduled', () => {
    const triage = task({ stage: 'inbox', iteration_id: 'it-1' });
    expect(taskInScope(triage, 'inbox', null)).toBe(true);
    expect(taskInScope(triage, 'current', 'it-1')).toBe(false);
    expect(taskInScope(task({ stage: 'inbox' }), 'backlog', null)).toBe(false);
  });

  it('splits triaged tasks between iterations and the backlog', () => {
    expect(taskInScope(task({ iteration_id: 'it-1' }), 'current', 'it-1')).toBe(true);
    expect(taskInScope(task({ iteration_id: 'it-1' }), 'next', 'it-2')).toBe(false);
    expect(taskInScope(task({}), 'backlog', null)).toBe(true);
    // A scope without an iteration yet shows nothing, not the backlog.
    expect(taskInScope(task({}), 'next', null)).toBe(false);
  });

  it('turns a drop on a scope into the fields to change', () => {
    expect(fieldsForScope(task({ stage: 'inbox' }), 'current', 'it-1')).toEqual({ stage: 'ready', iteration_id: 'it-1' });
    expect(fieldsForScope(task({ stage: 'inbox' }), 'current', 'it-1', 'qa')).toEqual({ stage: 'qa', iteration_id: 'it-1' });
    expect(fieldsForScope(task({ stage: 'review', iteration_id: 'it-1' }), 'backlog', null)).toEqual({ iteration_id: null });
    expect(fieldsForScope(task({ stage: 'done', iteration_id: 'it-1' }), 'inbox', null)).toEqual({ stage: 'inbox' });
    expect(fieldsForScope(task({ iteration_id: 'it-1' }), 'current', 'it-1')).toBeNull();
  });

  it('finds the scope a task lives in', () => {
    const scopes = scopeIterations(iterations, today);
    expect(scopeOfTask(task({ stage: 'inbox', iteration_id: 'it-1' }), scopes)).toBe('inbox');
    expect(scopeOfTask(task({}), scopes)).toBe('backlog');
    expect(scopeOfTask(task({ iteration_id: 'it-1' }), scopes)).toBe('current');
    expect(scopeOfTask(task({ iteration_id: 'it-0' }), scopes)).toBe('last');
    expect(scopeOfTask(task({ iteration_id: 'it-old' }), scopes)).toBeNull();
  });
});

describe('settings choices', () => {
  const { stages } = DEFAULT_TASKS_SETTINGS;

  it('maps keys and labels both ways, keeping unknown keys readable', () => {
    expect(choiceLabel(stages, 'in_progress')).toBe('In progress');
    expect(choiceLabel(stages, 'gone')).toBe('gone');
    expect(choiceFromLabel(stages, 'Review')).toBe('review');
    expect(choiceFromLabel(stages, 'Doing')).toBeNull();
    expect(choiceColor(stages, 'done')).toBe('green');
    expect(choiceColor(stages, 'gone')).toBe('slate');
  });

  it('starts with Inbox and ends with Done', () => {
    expect(stages[0].key).toBe('inbox');
    expect(stages[stages.length - 1].key).toBe('done');
  });
});

describe('matchesPriority', () => {
  it('keeps tasks of any selected priority, or without one', () => {
    expect(matchesPriority(task({ priority: 'high' }), [])).toBe(true);
    expect(matchesPriority(task({ priority: 'high' }), ['urgent', 'high'])).toBe(true);
    expect(matchesPriority(task({ priority: 'low' }), ['urgent'])).toBe(false);
    expect(matchesPriority(task({}), [NO_PRIORITY])).toBe(true);
    expect(matchesPriority(task({}), ['urgent'])).toBe(false);
  });
});

describe('matchesLabel', () => {
  it('keeps tasks with any selected label, or without one', () => {
    expect(matchesLabel(task({ labels: ['Bug', 'Data'] }), [])).toBe(true);
    expect(matchesLabel(task({ labels: ['Bug', 'Data'] }), ['Data'])).toBe(true);
    expect(matchesLabel(task({ labels: ['Bug'] }), ['Feature'])).toBe(false);
    expect(matchesLabel(task({}), [NO_LABEL])).toBe(true);
    expect(matchesLabel(task({ labels: ['Bug'] }), [NO_LABEL])).toBe(false);
  });
});

describe('matchesFilters', () => {
  const tasks = [
    task({ id: 'a', assignee_ids: ['u-1'], priority: 'high', labels: ['Bug'] }),
    task({ id: 'b', assignee_ids: ['u-1'], priority: 'low', labels: ['Feature'] }),
    task({ id: 'c', assignee_ids: ['u-2'], priority: 'high', labels: ['Bug', 'Data'] }),
    task({ id: 'd', priority: null, labels: [] }),
  ];
  const ids = (filters: Partial<typeof NO_FILTERS>) =>
    tasks.filter((t) => matchesFilters(t, { ...NO_FILTERS, ...filters })).map((t) => t.id);

  it('shows everything without filters', () => {
    expect(ids({})).toEqual(['a', 'b', 'c', 'd']);
  });

  it('combines filters with AND and values within one filter with OR', () => {
    expect(ids({ assignees: ['u-1'], priorities: ['high'] })).toEqual(['a']);
    expect(ids({ assignees: ['u-1', 'u-2'], labels: ['Bug'] })).toEqual(['a', 'c']);
    expect(ids({ priorities: ['high', 'low'], labels: ['Feature', 'Data'] })).toEqual(['b', 'c']);
    expect(ids({ assignees: ['u-1'], priorities: ['high'], labels: ['Feature'] })).toEqual([]);
  });

  it('selects tasks missing a value with the "none" options', () => {
    expect(ids({ assignees: [UNASSIGNED], priorities: [NO_PRIORITY], labels: [NO_LABEL] })).toEqual(['d']);
    expect(ids({ assignees: [UNASSIGNED, 'u-2'] })).toEqual(['c', 'd']);
  });
});

describe('matchesAssignee', () => {
  it('keeps tasks of any selected member, or unassigned ones', () => {
    const mine = task({ assignee_ids: ['u-1', 'u-2'] });
    const nobody = task({});
    expect(matchesAssignee(mine, [])).toBe(true);
    expect(matchesAssignee(nobody, [])).toBe(true);
    expect(matchesAssignee(mine, ['u-2'])).toBe(true);
    expect(matchesAssignee(mine, ['u-3', 'u-1'])).toBe(true);
    expect(matchesAssignee(nobody, ['u-2'])).toBe(false);
    expect(matchesAssignee(nobody, [UNASSIGNED])).toBe(true);
    expect(matchesAssignee(mine, [UNASSIGNED])).toBe(false);
  });
});
