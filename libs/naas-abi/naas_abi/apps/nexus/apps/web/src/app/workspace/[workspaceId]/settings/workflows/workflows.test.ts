import { describe, expect, it } from 'vitest';
import {
  fetchWorkflowSettings,
  filterWorkflows,
  workflowKey,
  type WorkflowSetting,
} from './workflows-model';

const item = (over: Partial<WorkflowSetting>): WorkflowSetting => ({
  type: 'workflow',
  module_id: 'acme.people',
  name: 'sync',
  display_name: 'sync',
  description: '',
  ...over,
});

const ITEMS = [
  item({ name: 'sync', display_name: 'Sync', description: 'Syncs the directory' }),
  item({ type: 'pipeline', name: 'pipeline.import', display_name: 'Import' }),
  item({ module_id: 'acme.market', name: 'prices', display_name: 'Prices' }),
];
const ALL = { query: '', type: 'all' };

describe('workflow settings', () => {
  it('sorts by module then name and filters by type and text', () => {
    expect(filterWorkflows(ITEMS, ALL).map((i) => i.name)).toEqual(['prices', 'pipeline.import', 'sync']);
    expect(filterWorkflows(ITEMS, { ...ALL, type: 'pipeline' }).map((i) => i.name)).toEqual([
      'pipeline.import',
    ]);
    expect(filterWorkflows(ITEMS, { ...ALL, query: 'directory' }).map((i) => i.name)).toEqual(['sync']);
  });

  it('keys an item by its type, module and name', () => {
    expect(workflowKey(ITEMS[1])).toBe('pipeline/acme.people/pipeline.import');
  });

  it('reads through the workspace API, with its words on a refusal', async () => {
    const calls: string[] = [];
    const ok = async (url: string) => {
      calls.push(url);
      return new Response(JSON.stringify({ workflows: ITEMS }), { status: 200 });
    };
    expect(await fetchWorkflowSettings('ws 1', ok)).toHaveLength(3);
    expect(calls).toEqual(['/api/workspaces/ws%201/workflows/settings']);
    const refused = async () =>
      new Response(JSON.stringify({ detail: 'You do not have permission to do this' }), { status: 403 });
    await expect(fetchWorkflowSettings('ws-1', refused)).rejects.toThrow(
      'You do not have permission to do this'
    );
  });
});
