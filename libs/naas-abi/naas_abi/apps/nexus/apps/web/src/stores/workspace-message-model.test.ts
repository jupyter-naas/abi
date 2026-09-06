import { beforeEach, describe, expect, it } from 'vitest';

import { useWorkspaceStore } from './workspace';

/**
 * The chat footer renders `message.modelId`. On send, the frontend seeds it
 * with the model the user has selected, but slides raise the model inside the
 * request. The backend announces the real model on the opening stream frame,
 * so the store needs a way to correct the streaming message. Without it a deck
 * written by Claude Sonnet 5 still reads "model: GPT-4.1 Mini".
 */
describe('setMessageModelId', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({
      currentWorkspaceId: 'ws-a',
      conversations: [],
      activeConversationId: null,
    });
  });

  const seedConversation = () => {
    const id = useWorkspaceStore.getState().createConversation();
    useWorkspaceStore.getState().addMessage(id, {
      role: 'assistant',
      content: '\u258c',
      modelId: 'gpt-4.1-mini',
    });
    const conv = useWorkspaceStore.getState().conversations.find((c) => c.id === id);
    return { conversationId: id, messageId: conv!.messages[conv!.messages.length - 1].id };
  };

  it('replaces the seeded model with the one the backend reports', () => {
    const { conversationId, messageId } = seedConversation();

    useWorkspaceStore
      .getState()
      .setMessageModelId(conversationId, messageId, 'anthropic/claude-sonnet-5');

    const conv = useWorkspaceStore.getState().conversations.find((c) => c.id === conversationId);
    const msg = conv!.messages.find((m) => m.id === messageId);
    expect(msg?.modelId).toBe('anthropic/claude-sonnet-5');
  });

  it('leaves other messages alone', () => {
    const { conversationId, messageId } = seedConversation();
    useWorkspaceStore.getState().addMessage(conversationId, {
      role: 'assistant',
      content: 'unrelated',
      modelId: 'gpt-4.1-mini',
    });

    useWorkspaceStore
      .getState()
      .setMessageModelId(conversationId, messageId, 'anthropic/claude-sonnet-5');

    const conv = useWorkspaceStore.getState().conversations.find((c) => c.id === conversationId);
    const others = conv!.messages.filter((m) => m.id !== messageId && m.role === 'assistant');
    expect(others.every((m) => m.modelId === 'gpt-4.1-mini')).toBe(true);
  });

  it('ignores an empty model so a missing field cannot blank the footer', () => {
    const { conversationId, messageId } = seedConversation();

    useWorkspaceStore.getState().setMessageModelId(conversationId, messageId, '');

    const conv = useWorkspaceStore.getState().conversations.find((c) => c.id === conversationId);
    const msg = conv!.messages.find((m) => m.id === messageId);
    expect(msg?.modelId).toBe('gpt-4.1-mini');
  });
});
