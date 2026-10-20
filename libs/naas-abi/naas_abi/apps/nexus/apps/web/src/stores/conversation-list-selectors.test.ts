import { readFileSync } from 'fs';
import path from 'path';

import { afterAll, beforeEach, describe, expect, it, vi } from 'vitest';

// Rename/pin/archive sync to the API; keep the test off the network.
vi.mock('./auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./auth')>()),
  authFetch: vi.fn(async () => ({ ok: true, json: async () => ({}) })),
}));

import { createConversationSummariesSelector } from './conversation-list-selectors';
import { selectSurfaceConversation } from './chat-thread-selectors';
import { useWorkspaceStore, type Conversation } from './workspace';

type WorkspaceState = ReturnType<typeof useWorkspaceStore.getState>;

const conversation = (overrides: Partial<Conversation> = {}): Conversation => ({
  id: 'conv-1',
  workspaceId: 'ws-a',
  title: 'Quarterly numbers',
  messages: [
    { id: 'u', role: 'user', content: 'Summarize Q3', timestamp: new Date('2026-08-06T19:48:31Z') },
    { id: 'a', role: 'assistant', content: '▌', timestamp: new Date('2026-08-06T19:48:31Z') },
  ],
  agent: 'abi',
  createdAt: new Date('2026-08-06T19:48:31Z'),
  updatedAt: new Date('2026-08-06T19:48:31Z'),
  ...overrides,
});

/**
 * Emulates `useWorkspaceStore(selector)`: zustand re-renders a subscriber only
 * when the selector output stops being Object.is-equal, so each identity change
 * counted here is one render of that component.
 */
function countRenders<T>(selector: (state: WorkspaceState) => T) {
  let previous = selector(useWorkspaceStore.getState());
  let renders = 0;
  const unsubscribe = useWorkspaceStore.subscribe((state) => {
    const next = selector(state);
    if (!Object.is(next, previous)) {
      renders += 1;
      previous = next;
    }
  });
  return {
    get renders() {
      return renders;
    },
    get value() {
      return previous;
    },
    unsubscribe,
  };
}

const streamChunks = (count: number) => {
  const { updateLastMessage } = useWorkspaceStore.getState();
  for (let i = 1; i <= count; i += 1) {
    updateLastMessage('conv-1', `token `.repeat(i));
  }
};

const networkCalls: string[] = [];
vi.stubGlobal('fetch', vi.fn(async (url: unknown) => {
  networkCalls.push(`${String(url)}\n${new Error().stack?.split('\n').slice(2, 9).join('\n')}`);
  return { ok: true, json: async () => ({}) };
}));
afterAll(() => {
  expect(networkCalls).toEqual([]);
});

beforeEach(() => {
  useWorkspaceStore.setState({
    currentWorkspaceId: 'ws-a',
    conversations: [
      conversation(),
      conversation({ id: 'conv-2', title: 'Other', updatedAt: new Date('2026-08-05T10:00:00Z') }),
      conversation({ id: 'conv-b', workspaceId: 'ws-b', title: 'Elsewhere' }),
    ],
    activeConversationId: 'conv-1',
    paneConversationId: null,
  });
});

describe('streaming does not re-render the sidebar or shell', () => {
  it('50 streamed chunks: full-store subscription renders 50 times, narrow selectors 0', () => {
    const fullStore = countRenders((s) => s);
    const summaries = countRenders(createConversationSummariesSelector());
    const shellWorkspaceCount = countRenders((s) => s.workspaces.length);
    const sidebarSections = countRenders((s) => s.expandedSections);
    const thread = countRenders((s) => selectSurfaceConversation(s, 'main'));

    streamChunks(50);

    expect(fullStore.renders).toBe(50); // what layout / ChatSection / CollapsibleSection did before
    expect(summaries.renders).toBe(0);
    expect(shellWorkspaceCount.renders).toBe(0);
    expect(sidebarSections.renders).toBe(0);
    expect(thread.renders).toBe(50); // the thread itself still repaints per chunk
    expect(thread.value?.messages.at(-1)?.content).toBe('token '.repeat(50));

    [fullStore, summaries, shellWorkspaceCount, sidebarSections, thread].forEach((t) => t.unsubscribe());
  });

  it('summaries omit messages and only list the current workspace', () => {
    const list = createConversationSummariesSelector()(useWorkspaceStore.getState());
    expect(list.map((c) => c.id)).toEqual(['conv-1', 'conv-2']);
    expect(list[0]).not.toHaveProperty('messages');
  });
});

describe('metadata changes still update the sidebar', () => {
  it('title, pin, archive, new message ordering and new conversations', () => {
    const summaries = countRenders(createConversationSummariesSelector());
    const store = useWorkspaceStore.getState();

    store.renameConversation('conv-2', 'Renamed');
    expect(summaries.renders).toBe(1);
    expect(summaries.value.find((c) => c.id === 'conv-2')?.title).toBe('Renamed');
    // The untouched row keeps its reference, so its memoized item does not re-render.
    const conv1 = summaries.value.find((c) => c.id === 'conv-1');

    store.togglePinConversation('conv-2');
    expect(summaries.value.find((c) => c.id === 'conv-2')?.pinned).toBe(true);
    store.toggleArchiveConversation('conv-2');
    expect(summaries.value.find((c) => c.id === 'conv-2')?.archived).toBe(true);
    expect(summaries.value.find((c) => c.id === 'conv-1')).toBe(conv1);

    const before = summaries.renders;
    store.addMessage('conv-1', { role: 'user', content: 'Follow-up' });
    expect(summaries.renders).toBe(before + 1); // updatedAt bumped by the new turn

    useWorkspaceStore.setState((s) => ({ conversations: [...s.conversations, conversation({ id: 'conv-3' })] }));
    expect(summaries.value.map((c) => c.id)).toContain('conv-3');
    summaries.unsubscribe();
  });

  it('switching workspace switches the list', () => {
    const summaries = countRenders(createConversationSummariesSelector());
    useWorkspaceStore.setState({ currentWorkspaceId: 'ws-b' });
    expect(summaries.value.map((c) => c.id)).toEqual(['conv-b']);
    useWorkspaceStore.setState({ currentWorkspaceId: null });
    expect(summaries.value).toEqual([]);
    summaries.unsubscribe();
  });

  it('a date restored as a string equals the same Date instant', () => {
    const select = createConversationSummariesSelector();
    const first = select(useWorkspaceStore.getState());
    useWorkspaceStore.setState((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === 'conv-1' ? { ...c, updatedAt: c.updatedAt.toISOString() as unknown as Date } : c
      ),
    }));
    expect(select(useWorkspaceStore.getState())).toBe(first);
  });
});

describe('shell components use narrow selectors', () => {
  const root = path.resolve(__dirname, '..');
  const read = (rel: string) => readFileSync(path.join(root, rel), 'utf8');

  it.each([
    'app/workspace/layout.tsx',
    'app/workspace/[workspaceId]/chat/components/chat-section.tsx',
    'components/shell/sidebar/collapsible-section.tsx',
    'components/shell/sidebar/apps-section.tsx',
    'components/shell/sidebar/files-section.tsx',
    'components/shell/sidebar/ontology-section.tsx',
    'components/shell/sidebar/settings-section.tsx',
    'components/shell/sidebar/search-section.tsx',
    'components/shell/sidebar/marketplace-section.tsx',
    'components/shell/context-panel.tsx',
  ])('%s does not subscribe to the whole workspace store', (rel) => {
    expect(read(rel)).not.toContain('useWorkspaceStore()');
  });

  it.each([
    'app/workspace/[workspaceId]/chat/components/chat-section.tsx',
    'app/workspace/[workspaceId]/chat/components/project-group.tsx',
  ])('%s passes stable callbacks to memoized conversation rows', (rel) => {
    // An inline closure is a new prop on every render and defeats React.memo,
    // so each sidebar render would re-render every conversation row.
    const rows = read(rel).match(/<ConversationItem[\s\S]*?\/>/g) ?? [];
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) expect(row).not.toContain('=>');
  });
});
