import { readFileSync } from 'fs';
import path from 'path';

import { beforeEach, describe, expect, it } from 'vitest';

import { selectSurfaceConversation, type ChatSurface } from './chat-thread-selectors';
import { useWorkspaceStore, type Conversation, type ToolCall } from './workspace';

/**
 * Regression guard for the chat thread going stale mid-stream.
 *
 * The thread subscribes to the store through `selectSurfaceConversation`. zustand
 * only re-renders a subscriber when its selector output stops being
 * `Object.is`-equal to the previous one, so "the UI repaints" and "the selector
 * output changes identity" are the same statement. These tests count the latter.
 *
 * The bug these guard against: the thread used to read its messages by calling
 * the `getWorkspaceConversations()` store action during render, while
 * subscribing to that action's (forever-stable) reference. Streamed tokens and
 * tool-call steps piled up in the store and the screen never repainted until an
 * unrelated state change or a manual page refresh forced it.
 */

const conversation = (overrides: Partial<Conversation> = {}): Conversation => ({
  id: 'conv-1',
  workspaceId: 'ws-a',
  title: 'Tweets ingested in the last 24 hours',
  messages: [
    {
      id: 'msg-user',
      role: 'user',
      content: 'How many tweets were ingested in the last 24 hours?',
      timestamp: new Date('2026-08-06T19:48:31Z'),
    },
    {
      id: 'msg-assistant',
      role: 'assistant',
      content: '▌',
      timestamp: new Date('2026-08-06T19:48:31Z'),
    },
  ],
  agent: 'abi',
  createdAt: new Date('2026-08-06T19:48:31Z'),
  updatedAt: new Date('2026-08-06T19:48:31Z'),
  ...overrides,
});

const step = (toolName: string, status: ToolCall['status']): ToolCall => ({
  id: `step-${toolName}`,
  toolName,
  rawName: toolName,
  prefix: 'Tool',
  status,
});

/**
 * Emulates what `useWorkspaceStore(selector)` does: recompute the selector on
 * every store write and count how many times the result changes identity. Each
 * increment is one React re-render of the thread.
 */
function trackRepaints(surface: ChatSurface) {
  const counter = { repaints: 0 };
  let previous = selectSurfaceConversation(useWorkspaceStore.getState(), surface);
  const unsubscribe = useWorkspaceStore.subscribe((state) => {
    const next = selectSurfaceConversation(state, surface);
    if (!Object.is(next, previous)) {
      counter.repaints += 1;
      previous = next;
    }
  });
  return {
    get repaints() {
      return counter.repaints;
    },
    get observed() {
      return previous;
    },
    unsubscribe,
  };
}

describe('selectSurfaceConversation', () => {
  beforeEach(() => {
    useWorkspaceStore.setState({
      currentWorkspaceId: 'ws-a',
      conversations: [conversation()],
      activeConversationId: 'conv-1',
      paneConversationId: null,
      contextPanelOpen: false,
    });
  });

  it('resolves the active conversation for the main surface', () => {
    const conv = selectSurfaceConversation(useWorkspaceStore.getState(), 'main');
    expect(conv?.id).toBe('conv-1');
  });

  it('repaints once per streamed chunk', () => {
    const tracker = trackRepaints('main');
    const { updateLastMessage } = useWorkspaceStore.getState();

    updateLastMessage('conv-1', 'Time window▌', undefined, undefined, 'Processing...', [
      step('Get Time Date', 'running'),
    ]);
    updateLastMessage('conv-1', 'Time window: last 24 hours▌', undefined, undefined, undefined, [
      step('Get Time Date', 'done'),
      step('Osint Pipeline Window Summary', 'running'),
    ]);
    updateLastMessage('conv-1', 'Time window: last 24 hours. 19 019 tweets.', 18.1, undefined, null, [
      step('Get Time Date', 'done'),
      step('Osint Pipeline Window Summary', 'done'),
    ]);

    // Three store writes, three repaints. On the regression this was 0 and the
    // thread only caught up when the user hit Refresh.
    expect(tracker.repaints).toBe(3);
    tracker.unsubscribe();
  });

  it('exposes the growing tool-call steps to subscribers as they arrive', () => {
    const tracker = trackRepaints('main');
    const { updateLastMessage } = useWorkspaceStore.getState();

    updateLastMessage('conv-1', '▌', undefined, undefined, undefined, [
      step('Get Time Date', 'running'),
    ]);
    expect(tracker.observed?.messages.at(-1)?.toolCalls).toEqual([
      step('Get Time Date', 'running'),
    ]);

    updateLastMessage('conv-1', '▌', undefined, undefined, undefined, [
      step('Get Time Date', 'done'),
      step('Osint Pipeline Window Summary', 'running'),
    ]);
    expect(tracker.observed?.messages.at(-1)?.toolCalls).toHaveLength(2);
    expect(tracker.observed?.messages.at(-1)?.toolCalls?.[0].status).toBe('done');

    tracker.unsubscribe();
  });

  it('stays narrow: unrelated store writes do not repaint the thread', () => {
    useWorkspaceStore.setState({
      conversations: [conversation(), conversation({ id: 'conv-2', messages: [] })],
    });
    const tracker = trackRepaints('main');

    useWorkspaceStore.getState().toggleContextPanel();
    expect(tracker.repaints).toBe(0);

    // A write to a *different* conversation must not repaint this thread either.
    useWorkspaceStore.getState().updateLastMessage('conv-2', 'unrelated');
    expect(tracker.repaints).toBe(0);

    tracker.unsubscribe();
  });

  it('keeps the compare pane independent of the main surface', () => {
    useWorkspaceStore.setState({
      conversations: [conversation(), conversation({ id: 'conv-pane' })],
      paneConversationId: 'conv-pane',
    });
    const pane = trackRepaints('pane');

    useWorkspaceStore.getState().updateLastMessage('conv-1', 'main surface token');
    expect(pane.repaints).toBe(0);

    useWorkspaceStore.getState().updateLastMessage('conv-pane', 'pane surface token');
    expect(pane.repaints).toBe(1);
    expect(pane.observed?.messages.at(-1)?.content).toBe('pane surface token');

    pane.unsubscribe();
  });

  it('returns undefined when the conversation belongs to another workspace', () => {
    useWorkspaceStore.setState({ currentWorkspaceId: 'ws-b' });
    expect(selectSurfaceConversation(useWorkspaceStore.getState(), 'main')).toBeUndefined();
  });

  it('returns undefined with no workspace or no selected conversation', () => {
    useWorkspaceStore.setState({ currentWorkspaceId: null });
    expect(selectSurfaceConversation(useWorkspaceStore.getState(), 'main')).toBeUndefined();

    useWorkspaceStore.setState({ currentWorkspaceId: 'ws-a', activeConversationId: null });
    expect(selectSurfaceConversation(useWorkspaceStore.getState(), 'main')).toBeUndefined();
  });
});

describe('chat thread subscription wiring', () => {
  it('does not read conversations through the non-reactive getWorkspaceConversations action', () => {
    // `getWorkspaceConversations` is a store *action*: selecting it returns the
    // same function reference forever, so a component that subscribes to it and
    // then calls it during render subscribes to nothing and freezes mid-stream.
    // The thread must use useSurfaceConversation() instead — see
    // chat-thread-selectors.ts for the full explanation.
    const source = readFileSync(
      path.resolve(__dirname, '../components/chat/chat-interface.tsx'),
      'utf8'
    );
    const code = source
      .split('\n')
      .filter((line) => !line.trim().startsWith('//'))
      .join('\n');

    expect(code).not.toContain('getWorkspaceConversations');
    expect(code).toContain('useSurfaceConversation(');
  });
});
