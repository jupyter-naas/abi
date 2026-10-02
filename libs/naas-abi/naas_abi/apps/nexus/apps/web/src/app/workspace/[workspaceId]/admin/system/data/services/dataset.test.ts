// @vitest-environment jsdom
import { createElement, Fragment } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { mount, type Mounted } from '../../system-render';
import type { ResourceDetail, ResourceEntry } from '../data-types';
import { TablePreview, csvProblem, datasetView, splitNames } from './dataset';

const table = (id: string, attributes: Record<string, string> = {}): ResourceEntry => ({
  id,
  name: id.split('/').pop() ?? id,
  kind: id.includes('/') ? 'item' : 'container',
  actions: id.includes('/') ? ['read', 'download', 'write', 'delete'] : [],
  size: null,
  modified: null,
  attributes,
});

const detail: ResourceDetail = {
  entry: table('github/commits', { rows: '2', columns: '3', primary_key: 'sha', partitions: 'day (month)' }),
  content: { encoding: 'text', text: 'sha,day,additions\n', size: 18, truncated: false },
  view: {
    type: 'table',
    columns: [
      { name: 'sha', type: 'string' },
      { name: 'day', type: 'date' },
      { name: 'additions', type: 'integer' },
    ],
    rows: [
      ['a1', '2026-10-01', 3],
      ['b2', '2026-10-02', null],
    ],
    total: 2,
    primary_key: ['sha'],
    partitions: [{ column: 'day', transform: 'month' }],
  },
};

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
});

describe('datasets view', () => {
  it('splits a table summary into chips and a remainder', () => {
    expect(splitNames('a, b, +3 more')).toEqual({ names: ['a', 'b'], more: '+3 more' });
    expect(splitNames('only')).toEqual({ names: ['only'], more: null });
    expect(splitNames(undefined)).toEqual({ names: [], more: null });
  });

  it('checks CSV headers before saving', () => {
    expect(csvProblem('# rows: 2\nid,name\n1,a\n')).toBeNull();
    expect(csvProblem('')).toMatch(/header row/);
    expect(csvProblem('id,,name')).toMatch(/empty column/);
    expect(csvProblem('id,name,id')).toMatch(/"id" appears twice/);
  });

  it('previews stats, the schema with key and partition, the rows and a query', async () => {
    mounted = await mount(TablePreview, { detail });
    const text = mounted.host.textContent ?? '';

    expect(mounted.host.querySelector('.data-dataset-stats')?.textContent).toContain('2');
    const columns = [...mounted.host.querySelectorAll('.data-dataset-column')].map((c) => c.textContent);
    expect(columns[0]).toContain('key');
    expect(columns[1]).toContain('by month');
    expect(mounted.host.querySelectorAll('.grid-table tbody tr')).toHaveLength(2);
    expect(mounted.host.querySelector('.grid-null')).not.toBeNull();
    expect(text).toContain('SELECT * FROM "commits" LIMIT 100');
  });

  it('shows namespaces as cards with their tables, and tables with their facts', async () => {
    const namespaces = datasetView.level?.(0, '');
    const tables = datasetView.level?.(1, 'github');
    const Cells = () =>
      createElement(
        Fragment,
        null,
        namespaces?.card?.(table('github', { tables: '9', summary: 'commits, issues, +7 more' })),
        ...(tables?.columns ?? []).map((c) => createElement('span', { key: c.id }, c.render(detail.entry))),
      );
    mounted = await mount(Cells, {});
    const chips = [...mounted.host.querySelectorAll('.data-dataset-chip')].map((c) => c.textContent);

    expect(namespaces?.layout).toBe('cards');
    expect(chips).toEqual(['commits', 'issues', '+7 more']);
    expect(mounted.host.textContent).toContain('sha');
    expect(tables?.columns?.map((c) => c.id)).toEqual(['rows', 'key']);
  });

  it('puts the column count, names and partitions on the name line', async () => {
    const entry = table('github/commits', { columns: '3', summary: 'sha, day, additions', partitions: 'day (month)' });
    const Line = () => createElement(Fragment, null, datasetView.summary?.(entry), datasetView.badges?.(entry));
    mounted = await mount(Line, {});

    expect(mounted.host.textContent).toBe('3 cols · sha, day, additionsday (month)');
  });

  it('never shows an unknown count as zero', async () => {
    const column = datasetView.level?.(0, '').columns?.[0];
    const Cell = () => createElement(Fragment, null, column?.render(table('github')));
    mounted = await mount(Cell, {});

    expect(mounted.host.textContent).toBe('—');
  });

  it('names tables like the warehouse does and states what dropping does', () => {
    const validate = datasetView.editor?.validateName;
    expect(validate?.('commits')).toBeNull();
    expect(validate?.('github/commits')).toBeNull();
    expect(validate?.('1bad')).not.toBeNull();
    expect(validate?.('a/b/c')).not.toBeNull();
    expect(datasetView.deleteWarning?.(table('github/commits', { rows: '1234' }))).toContain('1,234 rows');
    expect(datasetView.nounFor?.(table('github'), 0).one).toBe('namespace');
  });
});
