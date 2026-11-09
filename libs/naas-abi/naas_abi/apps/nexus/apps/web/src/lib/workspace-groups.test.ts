// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { existingWorkspaceGroups } from './workspace-groups';
import { clearViewFlag, setViewFlag } from './view-flag';

const rows = [
  { workspace_group: 'Sales ' },
  { workspace_group: 'Finance' },
  { workspace_group: null },
  { workspace_group: 'Sales' },
];
const answer = (status: number, body: unknown = rows) => async () => new Response(JSON.stringify(body), { status });

afterEach(() => clearViewFlag());

describe('the groups the organization already has (the Group picker of Settings › General)', () => {
  it('lists the distinct groups of the organization’s workspaces, sorted', async () => {
    expect(await existingWorkspaceGroups('acme', 'Sales', answer(200))).toEqual(['Finance', 'Sales']);
  });

  it('is empty for a workspace in no organization, and when the list cannot be read', async () => {
    expect(await existingWorkspaceGroups(undefined, '', answer(200))).toEqual([]);
    expect(await existingWorkspaceGroups('acme', '', answer(403, {}))).toEqual([]);
    expect(await existingWorkspaceGroups('acme', '', async () => Promise.reject(new Error('down')))).toEqual([]);
  });

  it('asks nothing in a view: the other workspaces of the organization are outside it, the picker shows the current group', async () => {
    setViewFlag({ workspaceId: 'ws-alpha', returnTo: null }, Date.now() + 15 * 60_000);
    let asked = 0;
    const fetcher = async () => {
      asked += 1;
      return new Response('[]', { status: 200 });
    };
    expect(await existingWorkspaceGroups('acme', 'Sales', fetcher)).toEqual(['Sales']);
    expect(await existingWorkspaceGroups('acme', '', fetcher)).toEqual([]);
    expect(asked).toBe(0);
  });
});
