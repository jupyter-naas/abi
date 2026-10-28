import { describe, expect, it } from 'vitest';
import {
  fetchWorkflowSettings,
  filterWorkflows,
  putWorkflowSetting,
  withSwitched,
  workflowKey,
  type WorkflowSetting,
} from './workflows-model';

const item = (over: Partial<WorkflowSetting>): WorkflowSetting => ({
  type: 'workflow',
  module_id: 'acme.people',
  name: 'sync',
  display_name: 'sync',
  description: '',
  enabled: true,
  ...over,
});

const ITEMS = [
  item({ name: 'sync', display_name: 'Sync', description: 'Syncs the directory' }),
  item({ type: 'pipeline', name: 'pipeline.import', display_name: 'Import', enabled: false }),
  item({ module_id: 'acme.market', name: 'prices', display_name: 'Prices' }),
];
const ALL = { query: '', type: 'all', status: 'all' };

describe('workflow settings', () => {
  it('sorts by module then name and filters by type, status and text', () => {
    expect(filterWorkflows(ITEMS, ALL).map((i) => i.name)).toEqual(['prices', 'pipeline.import', 'sync']);
    expect(filterWorkflows(ITEMS, { ...ALL, type: 'pipeline' }).map((i) => i.name)).toEqual([
      'pipeline.import',
    ]);
    expect(filterWorkflows(ITEMS, { ...ALL, status: 'disabled' }).map((i) => i.name)).toEqual([
      'pipeline.import',
    ]);
    expect(filterWorkflows(ITEMS, { ...ALL, query: 'directory' }).map((i) => i.name)).toEqual(['sync']);
  });

  it('switches one item by its type, module and name', () => {
    const key = workflowKey(ITEMS[1]);
    expect(key).toBe('pipeline/acme.people/pipeline.import');
    expect(withSwitched(ITEMS, key, true).map((i) => i.enabled)).toEqual([true, true, true]);
  });

  it('reads and records through the workspace API, with its words on a refusal', async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    const ok = async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ workflows: ITEMS }), { status: 200 });
    };
    expect(await fetchWorkflowSettings('ws 1', ok)).toHaveLength(3);
    await putWorkflowSetting('ws 1', ITEMS[0], false, ok);
    expect(calls[1].url).toBe('/api/workspaces/ws%201/workflows/settings');
    expect(calls[1].init?.method).toBe('PUT');
    expect(JSON.parse(String(calls[1].init?.body))).toEqual({
      type: 'workflow',
      module_id: 'acme.people',
      name: 'sync',
      enabled: false,
    });
    const refused = async () =>
      new Response(JSON.stringify({ detail: "This workflow is not in the workspace's set" }), {
        status: 403,
      });
    await expect(putWorkflowSetting('ws-1', ITEMS[0], true, refused)).rejects.toThrow(
      "This workflow is not in the workspace's set"
    );
  });
});
