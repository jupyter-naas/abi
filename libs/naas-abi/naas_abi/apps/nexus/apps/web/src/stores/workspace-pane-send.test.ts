import { beforeEach, describe, expect, it } from 'vitest';

import { useWorkspaceStore } from './workspace';

describe('pane send workspace scoping', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({
      currentWorkspaceId: 'ws-a',
      conversations: [],
      activeConversationId: null,
      paneConversationId: null,
      paneOpenTabIds: [],
      selectedAgent: 'agent-main',
      paneAgent: 'agent-pane',
    });
  });

  it('clears pane conversation when switching workspace', () => {
    const paneId = useWorkspaceStore.getState().createConversation(undefined, { surface: 'pane' });
    expect(useWorkspaceStore.getState().paneConversationId).toBe(paneId);
    expect(useWorkspaceStore.getState().paneOpenTabIds).toContain(paneId);

    useWorkspaceStore.getState().setCurrentWorkspace('ws-b');

    expect(useWorkspaceStore.getState().currentWorkspaceId).toBe('ws-b');
    expect(useWorkspaceStore.getState().paneConversationId).toBeNull();
    expect(useWorkspaceStore.getState().paneOpenTabIds).toEqual([]);
    expect(useWorkspaceStore.getState().activeConversationId).toBeNull();
  });

  it('keeps pane conversation when setCurrentWorkspace is a no-op same id', () => {
    const paneId = useWorkspaceStore.getState().createConversation(undefined, { surface: 'pane' });
    useWorkspaceStore.getState().setCurrentWorkspace('ws-a');
    expect(useWorkspaceStore.getState().paneConversationId).toBe(paneId);
  });

  it('creates pane drafts in the current workspace so send can find them', () => {
    const id = useWorkspaceStore.getState().createConversation(undefined, { surface: 'pane' });
    const conv = useWorkspaceStore.getState().conversations.find((c) => c.id === id);
    expect(conv?.workspaceId).toBe('ws-a');
    expect(conv?.isDraft).toBe(true);
    expect(useWorkspaceStore.getState().getWorkspaceConversations().some((c) => c.id === id)).toBe(
      true
    );
  });
});
