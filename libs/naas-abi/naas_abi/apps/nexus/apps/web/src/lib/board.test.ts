import { describe, expect, it } from 'vitest';
import {
  addWeeks,
  boardPath,
  iterationName,
  priorityFromLabel,
  stageFromLabel,
  toIsoDate,
  weekStart,
} from './board';

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
    expect(iterationName('2026-10-12', today)).toBe('Previous iteration');
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
  it('builds week, backlog and task links', () => {
    expect(boardPath('ws 1')).toBe('/workspace/ws%201/board');
    expect(boardPath('ws', { week: '2026-10-19' })).toBe('/workspace/ws/board?week=2026-10-19');
    expect(boardPath('ws', { backlog: true, week: '2026-10-19' })).toBe('/workspace/ws/board?backlog=1');
    expect(boardPath('ws', { week: '2026-10-19', task: 't1' })).toBe('/workspace/ws/board?week=2026-10-19&task=t1');
  });
});
