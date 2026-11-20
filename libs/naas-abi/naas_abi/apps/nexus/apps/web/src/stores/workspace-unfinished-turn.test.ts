import { beforeEach, describe, expect, it, vi } from 'vitest';

const authFetch = vi.hoisted(() => vi.fn());
vi.mock('./auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./auth')>()),
  authFetch,
}));

import { endsOnUnfinishedTurn } from '@/lib/unfinished-turn';
import { useWorkspaceStore } from './workspace';

const ANSWER = 'Here are the files in your workspace.';

/**
 * A reload during a delegated turn: the persisted thread ends on the caret of
 * a stream whose page went away, under a local id the server never saw. The
 * server ran the turn to its end and holds the answer.
 */
describe('loadConversationMessages after a turn its page left', () => {
  let conversationId = '';

  beforeEach(() => {
    useWorkspaceStore.setState({
      currentWorkspaceId: 'ws-a',
      conversations: [],
      activeConversationId: null,
    });
    conversationId = useWorkspaceStore.getState().createConversation();
    useWorkspaceStore.getState().addMessage(conversationId, {
      role: 'user',
      content: 'List my files',
    });
    useWorkspaceStore.getState().addMessage(conversationId, { role: 'assistant', content: '▌' });
    authFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: conversationId,
        workspace_id: 'ws-a',
        messages: [
          { id: 'msg-user', role: 'user', content: 'List my files' },
          { id: 'msg-answer', role: 'assistant', content: ANSWER },
        ],
      }),
    });
  });

  const thread = () =>
    useWorkspaceStore.getState().conversations.find((c) => c.id === conversationId)!.messages;

  it('shows the server answer in place of the caret with replaceLocal', async () => {
    expect(endsOnUnfinishedTurn(thread())).toBe(true);

    await useWorkspaceStore.getState().loadConversationMessages(conversationId, {
      replaceLocal: true,
    });

    expect(thread().map((m) => m.content)).toEqual(['List my files', ANSWER]);
    expect(endsOnUnfinishedTurn(thread())).toBe(false);
  });

  it('keeps the local caret after the answer without it', async () => {
    await useWorkspaceStore.getState().loadConversationMessages(conversationId);

    expect(endsOnUnfinishedTurn(thread())).toBe(true);
  });
});
