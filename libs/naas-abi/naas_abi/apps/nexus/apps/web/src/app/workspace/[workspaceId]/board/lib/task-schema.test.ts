import { describe, expect, it } from 'vitest';
import { DEFAULT_BOARD_SETTINGS, type BoardTask } from '@/lib/board';
import { sanitizeViews } from '@/components/database-view/use-database-views';
import { BACKLOG_VIEWS, INBOX_VIEWS, ITERATION_VIEWS, createTaskSchema } from './task-schema';

const task = (overrides: Partial<BoardTask> & Pick<BoardTask, 'id' | 'title'>): BoardTask => ({
  workspace_id: 'ws',
  content: '',
  stage: 'inbox',
  iteration_id: null,
  project: '',
  priority: null,
  due_date: null,
  labels: [],
  assignee_ids: [],
  archived: false,
  archived_at: null,
  created_by: 'u-1',
  created_at: '2026-10-20T09:00:00',
  updated_by: 'u-1',
  updated_at: '2026-10-20T09:00:00',
  ...overrides,
});

const schema = createTaskSchema({
  memberName: (id) => ({ 'u-1': 'Ada', 'u-2': 'Grace' })[id] ?? 'Former member',
  iterationLabel: () => 'Oct 19 – Oct 25',
  settings: DEFAULT_BOARD_SETTINGS,
});

const tasks = [
  task({ id: 'a', title: 'Alpha', stage: 'review', priority: 'low', assignee_ids: ['u-2'], project: 'Nexus' }),
  task({ id: 'b', title: 'Bravo', stage: 'inbox', priority: 'urgent', labels: ['Bug', 'Data'] }),
  task({ id: 'c', title: 'Charlie', stage: 'review', due_date: '2026-11-02', project: 'Abi' }),
];

const titles = (rows: BoardTask[]) => rows.map((t) => t.title);

describe('task schema', () => {
  it('groups by stage in workflow order, including empty stages', () => {
    const groups = schema.groupRecords(tasks, 'stage');
    expect(groups.map((g) => g.label)).toEqual(['Inbox', 'Ready', 'In progress', 'On hold', 'Review', 'Done']);
    expect(titles(groups[4].records)).toEqual(['Alpha', 'Charlie']);
    expect(groups[1].records).toEqual([]);
  });

  it('sorts priorities from urgent to low, unset last', () => {
    expect(titles(schema.applySort(tasks, { property: 'priority', direction: 'asc' }))).toEqual([
      'Bravo', 'Alpha', 'Charlie',
    ]);
  });

  it('sorts due dates chronologically on the raw date', () => {
    const rows = [...tasks, task({ id: 'd', title: 'Delta', due_date: '2026-10-30' })];
    expect(titles(schema.applySort(rows, { property: 'due_date', direction: 'asc' }))).toEqual([
      'Delta', 'Charlie', 'Alpha', 'Bravo',
    ]);
  });

  it('filters and groups by project, labels and assignee names', () => {
    expect(titles(schema.applyFilters(tasks, [{ id: 'f', property: 'project', operator: 'is', value: 'nexus' }]))).toEqual(['Alpha']);
    expect(titles(schema.applyFilters(tasks, [{ id: 'f', property: 'labels', operator: 'is', value: 'Bug' }]))).toEqual(['Bravo']);
    expect(titles(schema.applyFilters(tasks, [{ id: 'f', property: 'assignees', operator: 'is', value: 'Grace' }]))).toEqual(['Alpha']);
    expect(schema.groupRecords(tasks, 'project').map((g) => g.key)).toEqual(['Abi', 'Nexus', '__empty__']);
  });

  it('groups the inbox by creation day, newest day first', () => {
    const rows = [
      task({ id: 'd1', title: 'Early', created_at: '2026-10-21T08:00:00' }),
      task({ id: 'd2', title: 'Late', created_at: '2026-10-22T15:00:00' }),
      task({ id: 'd3', title: 'Morning', created_at: '2026-10-22T09:00:00' }),
    ];
    const sorted = schema.applySort(rows, { property: 'created_at', direction: 'desc' });
    const groups = schema.groupRecords(sorted, 'created_at', 'desc');
    expect(groups).toHaveLength(2);
    expect(titles(groups[0].records)).toEqual(['Late', 'Morning']);
    expect(titles(groups[1].records)).toEqual(['Early']);
    expect(schema.groupableProperties.map((p) => p.key)).toContain('created_at');
  });

  it('groups the backlog by priority from urgent to low, unset last', () => {
    const groups = schema.groupRecords(tasks, 'priority').filter((g) => g.records.length > 0);
    expect(groups.map((g) => g.label)).toEqual(['Urgent', 'Low', 'No priority']);
  });

  it('searches titles and resolved names', () => {
    expect(titles(schema.applySearch(tasks, 'grace'))).toEqual(['Alpha']);
  });
});

describe('task views', () => {
  it('shows iterations as stage columns and Inbox / Backlog as tables', () => {
    const [iteration] = ITERATION_VIEWS.defaultViews();
    expect(iteration.type).toBe('board');
    expect(iteration.groupBy).toBe('stage');
    const [inbox] = INBOX_VIEWS.defaultViews();
    expect(inbox.type).toBe('table');
    expect(inbox.groupBy).toBe('created_at');
    expect(inbox.sort).toEqual({ property: 'created_at', direction: 'desc' });
    const [backlog] = BACKLOG_VIEWS.defaultViews();
    expect(backlog.type).toBe('table');
    expect(backlog.groupBy).toBe('priority');
  });

  it('keeps each kind of tab in its own storage', () => {
    const prefixes = [ITERATION_VIEWS, INBOX_VIEWS, BACKLOG_VIEWS].map((v) => v.storagePrefix);
    expect(new Set(prefixes).size).toBe(3);
  });

  it('drops saved views that reference unknown properties or layouts', () => {
    const views = sanitizeViews(
      [
        { id: '1', name: 'Mine', type: 'board', visible: ['priority', 'nope', 'title'], filters: [], sort: null, groupBy: 'stage' },
        { id: '2', name: 'Old', type: 'list', visible: [], filters: [], sort: null, groupBy: null },
      ],
      ITERATION_VIEWS,
    );
    expect(views).toHaveLength(1);
    expect(views?.[0].visible).toEqual(['priority']);
  });
});
