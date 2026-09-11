import { beforeEach, describe, expect, it } from 'vitest';

import type { Agent } from '@/stores/agents';
import { useAgentsStore } from '@/stores/agents';
import { useFeaturePaneStore } from '@/stores/feature-pane';
import { useWorkspaceStore } from '@/stores/workspace';

import { bindFeaturePaneAgent, openFeatureAgentPane } from './feature-agent-pane';

const DEFAULT_ID = 'agent-default';
const ABI_ID = 'agent-abi';
const APPS_ID = 'agent-apps';
const SLIDES_ID = 'agent-slides';

function seedAgents(withApps = true, withDefault = true): void {
  useAgentsStore.setState({
    agents: [
      {
        id: DEFAULT_ID,
        name: 'Bob',
        class_name: 'bob.agents.BobAgent/BobAgent',
        enabled: true,
        isDefault: withDefault,
      } as Agent,
      {
        id: ABI_ID,
        name: 'Abi',
        class_name: 'naas_abi.agents.AbiAgent/AbiAgent',
        enabled: true,
        isDefault: false,
      } as Agent,
      {
        id: SLIDES_ID,
        name: 'Slides',
        class_name: 'naas_abi.agents.SlidesAgent/SlidesAgent',
        enabled: true,
        isDefault: false,
      } as Agent,
      ...(withApps
        ? [
            {
              id: APPS_ID,
              name: 'Apps',
              class_name: 'naas_abi.agents.AppsAgent/AppsAgent',
              enabled: true,
              isDefault: false,
            } as Agent,
          ]
        : []),
    ],
  });
}

beforeEach(() => {
  seedAgents();
  useWorkspaceStore.setState({
    contextPanelOpen: false,
    paneAgent: '',
    paneAgentExplicitlySelected: false,
    paneConversationId: null,
    conversations: [],
  });
});

describe('bindFeaturePaneAgent', () => {
  it('binds the Apps agent on the Apps section', () => {
    expect(bindFeaturePaneAgent('apps')).toBe(APPS_ID);
    expect(useWorkspaceStore.getState().paneAgent).toBe(APPS_ID);
  });

  it('binds the workspace default when Apps is not on the roster', () => {
    seedAgents(false);
    bindFeaturePaneAgent('apps');
    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
  });

  it('binds the workspace default on Home, not Abi', () => {
    bindFeaturePaneAgent(null);
    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
  });

  it('binds Abi on Home and Chat when the workspace has no default', () => {
    seedAgents(true, false);
    bindFeaturePaneAgent(null);
    expect(useWorkspaceStore.getState().paneAgent).toBe(ABI_ID);
    bindFeaturePaneAgent('chat');
    expect(useWorkspaceStore.getState().paneAgent).toBe(ABI_ID);
  });

  it('puts an auto-bound pane back on the default on Chat', () => {
    bindFeaturePaneAgent('apps');
    bindFeaturePaneAgent('chat');
    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
  });

  it('keeps an explicit picker choice when nothing is open', () => {
    useWorkspaceStore.getState().setPaneAgent(DEFAULT_ID, true);
    bindFeaturePaneAgent('apps');
    expect(useWorkspaceStore.getState().paneAgent).toBe(DEFAULT_ID);
    expect(useWorkspaceStore.getState().paneAgentExplicitlySelected).toBe(true);
  });

  it('overrides an explicit choice when an item is open', () => {
    useWorkspaceStore.getState().setPaneAgent(DEFAULT_ID, true);
    bindFeaturePaneAgent('apps', { force: true });
    expect(useWorkspaceStore.getState().paneAgent).toBe(APPS_ID);
  });

  it('replaces an explicit choice that left the roster', () => {
    useWorkspaceStore.getState().setPaneAgent('agent-from-another-workspace', true);
    bindFeaturePaneAgent('apps');
    expect(useWorkspaceStore.getState().paneAgent).toBe(APPS_ID);
  });
});

describe('openFeatureAgentPane', () => {
  it('opens the pane and binds the feature agent', () => {
    openFeatureAgentPane('apps');
    const ws = useWorkspaceStore.getState();
    expect(ws.contextPanelOpen).toBe(true);
    expect(ws.paneAgent).toBe(APPS_ID);
  });

  it('starts a blank thread and drops the picker choice on freshChat', () => {
    useWorkspaceStore.setState({ paneConversationId: 'conv-1' });
    useWorkspaceStore.getState().setPaneAgent(DEFAULT_ID, true);
    openFeatureAgentPane('apps', { freshChat: true });
    const ws = useWorkspaceStore.getState();
    expect(ws.paneConversationId).toBeNull();
    expect(ws.paneAgentExplicitlySelected).toBe(false);
    expect(ws.paneAgent).toBe(APPS_ID);
  });

  it('forces the feature agent when a resource is open', () => {
    useWorkspaceStore.getState().setPaneAgent(DEFAULT_ID, true);
    openFeatureAgentPane('apps', { resourceId: 'acme.module:wsr' });
    expect(useWorkspaceStore.getState().paneAgent).toBe(APPS_ID);
  });
});

describe('useFeaturePaneStore', () => {
  const wsr = { feature: 'apps' as const, kind: 'app', id: 'acme.module:wsr' };
  const docs = { feature: 'apps' as const, kind: 'app', id: 'acme.module:docs' };

  beforeEach(() => useFeaturePaneStore.setState({ resource: null }));

  it('clears only the resource that is still published', () => {
    useFeaturePaneStore.getState().setResource(docs);
    useFeaturePaneStore.getState().clearResource(wsr);
    expect(useFeaturePaneStore.getState().resource).toEqual(docs);

    useFeaturePaneStore.getState().clearResource(docs);
    expect(useFeaturePaneStore.getState().resource).toBeNull();
  });
});
