import { describe, expect, it } from 'vitest';
import { createWorkspaceResourcesStore } from '@/hooks/use-workspace-resources';
import type { ResourcesAnswer, WorkspaceResources } from '@/lib/workspace-resources';

const resources = (apps: number): WorkspaceResources => ({
  organization_id: 'org-1',
  can_edit_set: true,
  features: ['apps', 'settings'],
  modules: [],
  totals: { agents: 0, apps, workflows: 0, pipelines: 0 },
});

function scripted(...answers: ResourcesAnswer[]) {
  const calls: string[] = [];
  const fetcher = async (workspaceId: string) => {
    calls.push(workspaceId);
    return answers.shift() ?? { kind: 'failed' as const };
  };
  return { calls, store: createWorkspaceResourcesStore(fetcher) };
}

const appsOf = (store: ReturnType<typeof createWorkspaceResourcesStore>) =>
  store.getState().byWorkspace['ws-1']?.resources?.totals.apps;

describe('workspace resources store', () => {
  it('keeps a known answer until asked again, then reads the new set', async () => {
    const { calls, store } = scripted({ kind: 'ok', resources: resources(0) }, { kind: 'ok', resources: resources(2) });
    await store.getState().load('ws-1');
    await store.getState().load('ws-1');
    expect(calls).toHaveLength(1);
    expect(appsOf(store)).toBe(0);
    // The settings opened again, or Reload: the set changed on Modules & features.
    await store.getState().load('ws-1', true);
    expect(calls).toHaveLength(2);
    expect(appsOf(store)).toBe(2);
  });

  it('never keeps a failed read: the last answer stays, and none is read again', async () => {
    const { calls, store } = scripted(
      { kind: 'failed' },
      { kind: 'ok', resources: resources(1) },
      { kind: 'failed' }
    );
    await store.getState().load('ws-1');
    expect(store.getState().byWorkspace['ws-1']).toEqual({ status: 'ready', resources: null });
    await store.getState().load('ws-1');
    expect(appsOf(store)).toBe(1);
    await store.getState().load('ws-1', true);
    expect(appsOf(store)).toBe(1);
    expect(calls).toHaveLength(3);
  });

  it('shares the call in flight', async () => {
    const { calls, store } = scripted({ kind: 'ok', resources: resources(1) });
    await Promise.all([store.getState().load('ws-1'), store.getState().load('ws-1', true)]);
    expect(calls).toHaveLength(1);
  });

  it('reads nothing for a caller who may not, and asks again later', async () => {
    const { calls, store } = scripted({ kind: 'denied' }, { kind: 'denied' });
    await store.getState().load('ws-1');
    await store.getState().load('ws-1');
    expect(store.getState().byWorkspace['ws-1'].resources).toBeNull();
    expect(calls).toHaveLength(2);
  });
});
