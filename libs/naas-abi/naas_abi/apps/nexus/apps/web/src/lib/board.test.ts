import { describe, expect, it } from 'vitest';
import {
  UNASSIGNED,
  addWeeks,
  boardPath,
  fieldsForScope,
  iterationName,
  matchesAssignee,
  parseScope,
  priorityFromLabel,
  scopeOfTask,
  scopeWeek,
  stageFromLabel,
  taskInScope,
  toIsoDate,
  weekStart,
  type BoardTask,
} from './board';

const task = (overrides: Partial<BoardTask>): BoardTask => ({
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

describe('iterationName', () => {
  it('names the current, previous and next weeks', () => {
    const today = '2026-10-22';
    expect(iterationName('2026-10-19', today)).toBe('Current iteration');
    expect(iterationName('2026-10-12', today)).toBe('Last iteration');
    expect(iterationName('2026-10-26', today)).toBe('Next iteration');
    expect(iterationName('2026-11-02', today)).toMatch(/^Week of /);
  });
});

describe('labels', () => {
  it('maps display labels back to stage and priority ids', () => {
    expect(stageFromLabel('In progress')).toBe('in_progress');
    expect(stageFromLabel('Doing')).toBeNull();
    expect(priorityFromLabel('Urgent')).toBe('urgent');
  });
});

describe('boardPath', () => {
  it('builds scope and task links; the current iteration is the default', () => {
    expect(boardPath('ws 1')).toBe('/workspace/ws%201/board');
    expect(boardPath('ws', { view: 'current' })).toBe('/workspace/ws/board');
    expect(boardPath('ws', { view: 'backlog' })).toBe('/workspace/ws/board?view=backlog');
    expect(boardPath('ws', { view: 'next', task: 't1' })).toBe('/workspace/ws/board?view=next&task=t1');
    expect(boardPath('ws', { view: 'inbox', newTask: true })).toBe('/workspace/ws/board?view=inbox&new=1');
  });

  it('reads unknown views as the current iteration', () => {
    expect(parseScope('inbox')).toBe('inbox');
    expect(parseScope('week')).toBe('current');
    expect(parseScope(null)).toBe('current');
  });
});

describe('scopes', () => {
  const current = '2026-10-19';

  it('maps iteration scopes to their week', () => {
    expect(scopeWeek('current', current)).toBe('2026-10-19');
    expect(scopeWeek('last', current)).toBe('2026-10-12');
    expect(scopeWeek('next', current)).toBe('2026-10-26');
    expect(scopeWeek('inbox', current)).toBeNull();
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
    // A week without an iteration yet shows nothing, not the backlog.
    expect(taskInScope(task({}), 'next', null)).toBe(false);
  });

  it('turns a drop on a scope into the fields to change', () => {
    expect(fieldsForScope(task({ stage: 'inbox' }), 'current', 'it-1')).toEqual({ stage: 'ready', iteration_id: 'it-1' });
    expect(fieldsForScope(task({ stage: 'review', iteration_id: 'it-1' }), 'backlog', null)).toEqual({ iteration_id: null });
    expect(fieldsForScope(task({ stage: 'done', iteration_id: 'it-1' }), 'inbox', null)).toEqual({ stage: 'inbox' });
    expect(fieldsForScope(task({ iteration_id: 'it-1' }), 'current', 'it-1')).toBeNull();
  });

  it('finds the scope a task lives in', () => {
    const weeks: Record<string, string> = { 'it-1': '2026-10-19', 'it-0': '2026-10-12', 'it-old': '2026-09-28' };
    const week = (id: string) => weeks[id] ?? null;
    expect(scopeOfTask(task({ stage: 'inbox', iteration_id: 'it-1' }), week, current)).toBe('inbox');
    expect(scopeOfTask(task({}), week, current)).toBe('backlog');
    expect(scopeOfTask(task({ iteration_id: 'it-1' }), week, current)).toBe('current');
    expect(scopeOfTask(task({ iteration_id: 'it-0' }), week, current)).toBe('last');
    expect(scopeOfTask(task({ iteration_id: 'it-old' }), week, current)).toBeNull();
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
