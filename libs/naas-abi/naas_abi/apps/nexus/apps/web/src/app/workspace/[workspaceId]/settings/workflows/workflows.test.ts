import { describe, expect, it } from 'vitest';
import {
  WORKFLOW_EXPORT_HEADERS,
  fetchWorkflowSettings,
  sortedWorkflows,
  workflowCellValues,
  workflowExportRow,
  workflowKey,
  workflowSearchTexts,
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

describe('workflow settings', () => {
  it('sorts by module then name', () => {
    expect(sortedWorkflows(ITEMS).map((i) => i.name)).toEqual(['prices', 'pipeline.import', 'sync']);
  });

  it('gives each column the values its filter sees, and the search its texts', () => {
    expect(workflowCellValues(ITEMS[1], 'name')).toEqual(['Import']);
    expect(workflowCellValues(ITEMS[1], 'type')).toEqual(['pipeline']);
    expect(workflowCellValues(ITEMS[2], 'module')).toEqual(['acme.market']);
    expect(workflowSearchTexts(ITEMS[0])).toEqual(['Sync', 'sync', 'acme.people', 'Syncs the directory']);
  });

  it('exports a row with its key, type, module and description', () => {
    expect(WORKFLOW_EXPORT_HEADERS).toEqual(['Name', 'Key', 'Type', 'Module', 'Description']);
    expect(workflowExportRow(ITEMS[0])).toEqual(['Sync', 'sync', 'workflow', 'acme.people', 'Syncs the directory']);
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
