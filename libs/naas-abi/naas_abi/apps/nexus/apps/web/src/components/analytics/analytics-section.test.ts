// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount, type Mounted } from '@/lib/testing/mount';

const state = vi.hoisted(() => ({
  seen: [] as string[],
  access: {} as Record<string, unknown>,
}));

const EMPTY_OVERVIEW = {
  kpi: {
    active_users: 2,
    total_sessions: 3,
    avg_sessions_per_user: 1.5,
    total_page_views: 9,
    workspaces_used: 1,
    avg_session_duration_seconds: 60,
    returning_users: 1,
    most_active_workspace: null,
  },
  period: {
    period: 'today',
    date_start: '2026-11-19T00:00:00+01:00',
    date_end: '2026-11-19T10:00:00+01:00',
    timezone: 'Europe/Paris',
    granularity: 'hour',
  },
  sessions_over_time: [{ date: '2026-11-19T09', value: 3 }],
  active_users_over_time: [{ date: '2026-11-19T09', value: 2 }],
  top_users: [],
  top_pages: [],
  workspace_activity: [],
  recent_activity: [],
};

const CHAT_ANALYTICS = {
  kpi: {
    num_chats: 1,
    num_messages: 4,
    messages_liked: 1,
    messages_disliked: 0,
    agents_used: 1,
    tools_used: 0,
  },
  messages_over_time: [],
  chats_over_time: [],
  top_agents: [],
  top_tools: [],
  feedback_distribution: [],
  top_chats: [
    {
      conversation_id: 'conv-1',
      title: 'Quarterly plan',
      user_email: 'ann@acme.test',
      message_count: 4,
      likes: 1,
      dislikes: 0,
      agents: ['abi'],
      tools: [],
      last_message_at: '2026-11-19T08:00:00Z',
    },
  ],
};

function answer(url: string): unknown {
  const path = url.split('?')[0];
  if (path.endsWith('/access')) return state.access[path] ?? { can_read: false };
  if (path.endsWith('/overview')) return EMPTY_OVERVIEW;
  if (path.endsWith('/users')) {
    return { users: [], directory: [{ user_id: 'u-ann', user_email: 'ann@acme.test', workspace_ids: ['ws-1'] }] };
  }
  if (path.endsWith('/workspaces')) return { workspaces: [], directory: [{ workspace_id: 'ws-1', workspace_name: 'Sales' }] };
  if (path.endsWith('/chat-analytics')) return CHAT_ANALYTICS;
  if (path.includes('/users/')) {
    return {
      user_id: 'u-ann',
      user_email: 'ann@acme.test',
      first_seen: '2026-11-19T08:00:00Z',
      last_seen: '2026-11-19T09:00:00Z',
      total_sessions: 1,
      total_page_views: 2,
      workspaces_used: [],
      most_visited_page: null,
      sessions: [],
      pages: [],
      events: [],
    };
  }
  if (path.includes('/chats/')) {
    return { conversation_id: 'conv-1', workspace_id: 'ws-e', user_id: 'u-ann', title: 'Quarterly plan', agent: 'abi', messages: [] };
  }
  return {};
}

vi.mock('@/stores/auth', () => {
  const store = { user: { id: 'u-admin' } };
  const useAuthStore = Object.assign((select: (s: typeof store) => unknown) => select(store), {
    persist: { hasHydrated: () => true, onFinishHydration: () => () => undefined },
  });
  return {
    useAuthStore,
    authFetch: async (url: string) => {
      state.seen.push(url);
      return new Response(JSON.stringify(answer(url)), { status: 200 });
    },
  };
});

// Which heavy tab modules were evaluated (#1609): Chats and a user's detail load on open.
const loadedTabs = vi.hoisted(() => [] as string[]);
vi.mock('./tabs/chats-tab', async (original) => (loadedTabs.push('chats'), original()));
vi.mock('./tabs/user-detail', async (original) => (loadedTabs.push('user-detail'), original()));

import { AnalyticsSection } from './analytics-section';
import type { AnalyticsScope } from './scope';

let mounted: Mounted | null = null;
afterEach(async () => {
  await mounted?.unmount();
  mounted = null;
  state.seen = [];
});

async function render(scope: AnalyticsScope): Promise<Mounted> {
  mounted = await mount(AnalyticsSection, { scope });
  for (let i = 0; i < 4; i += 1) await mounted.flush();
  return mounted;
}

/** Flush until ``ready``: a tab other than Overview loads its code on first open. */
async function until(m: Mounted, ready: () => boolean) {
  await vi.waitFor(async () => {
    await m.flush();
    expect(ready()).toBe(true);
  });
}
const chatRow = (m: Mounted) =>
  Array.from(m.host.querySelectorAll('tr')).find((tr) => tr.textContent?.includes('Quarterly plan'));

const buttons = (m: Mounted) => Array.from(m.host.querySelectorAll('button'));
const button = (m: Mounted, label: string) => buttons(m).find((b) => b.textContent?.trim() === label) ?? null;

describe('AnalyticsSection', () => {
  // First in the file: it checks which tab modules were evaluated since the file started.
  it('loads neither Chats nor a user detail until one is opened, then that one alone', async () => {
    state.access['/api/organizations/org-z/analytics/access'] = { can_read: true, can_read_conversations: false };
    const m = await render({ kind: 'organization', orgId: 'org-z' });
    expect(m.host.textContent).toContain('Times in');
    expect(loadedTabs).toEqual([]);

    await m.click(button(m, 'Chats'));
    await until(m, () => Boolean(chatRow(m)));
    expect(loadedTabs).toEqual(['chats']);
  });

  it('reads a workspace under its own base, with no Workspaces tab nor workspace filter', async () => {
    state.access['/api/workspaces/ws-a/analytics/access'] = {
      can_read: true,
      can_read_conversations: false,
      timezone: 'Europe/Paris',
    };
    const m = await render({ kind: 'workspace', workspaceId: 'ws-a' });
    const text = m.host.textContent ?? '';
    expect(text).toContain('Times in Europe/Paris');
    expect(['Today', 'Yesterday', 'This week', 'This month'].every((label) => button(m, label))).toBe(true);
    expect(button(m, 'Workspaces')).toBeNull();
    expect(text).not.toContain('All workspaces');
    expect(state.seen).toContain('/api/workspaces/ws-a/analytics/overview?period=today');
    expect(state.seen.some((url) => url.includes('/api/organizations/'))).toBe(false);
    expect(state.seen.some((url) => url.includes('/workspaces?'))).toBe(false);

    await m.click(button(m, 'This week'));
    await m.flush();
    expect(state.seen).toContain('/api/workspaces/ws-a/analytics/overview?period=this_week');
  });

  it('reads an organization with its Workspaces tab and filter', async () => {
    state.access['/api/organizations/org-b/analytics/access'] = { can_read: true, timezone: 'UTC' };
    const m = await render({ kind: 'organization', orgId: 'org-b' });
    expect(button(m, 'Workspaces')).not.toBeNull();
    expect(m.host.textContent).toContain('All workspaces');
    expect(state.seen).toContain('/api/organizations/org-b/analytics/overview?period=today');
    expect(state.seen).toContain('/api/organizations/org-b/analytics/workspaces?period=today');
  });

  it('says so when the caller may not read the scope', async () => {
    state.access['/api/workspaces/ws-c/analytics/access'] = { can_read: false };
    const m = await render({ kind: 'workspace', workspaceId: 'ws-c' });
    expect(m.host.textContent).toContain('You cannot read these analytics');
    expect(m.host.textContent).not.toContain('Times in');
    expect(state.seen).toContain('/api/workspaces/ws-c/analytics/access');
  });

  it('lists chats as metadata only without the conversation right: no message view', async () => {
    state.access['/api/workspaces/ws-d/analytics/access'] = { can_read: true, can_read_conversations: false };
    const m = await render({ kind: 'workspace', workspaceId: 'ws-d' });
    await m.click(button(m, 'Chats'));
    await until(m, () => Boolean(chatRow(m)));
    expect(m.host.textContent).toContain('Metadata only');
    const row = Array.from(m.host.querySelectorAll('tr')).find((tr) => tr.textContent?.includes('Quarterly plan'));
    expect(row).toBeTruthy();
    await m.click(row as Element);
    await m.flush();
    expect(state.seen.some((url) => url.includes('/chats/conv-1'))).toBe(false);
    expect(m.host.textContent).not.toContain('Conversation has no stored messages');
  });

  it('opens a conversation for a caller holding the conversation right', async () => {
    state.access['/api/workspaces/ws-e/analytics/access'] = { can_read: true, can_read_conversations: true };
    const m = await render({ kind: 'workspace', workspaceId: 'ws-e' });
    await m.click(button(m, 'Chats'));
    await until(m, () => Boolean(chatRow(m)));
    expect(m.host.textContent).not.toContain('Metadata only');
    const row = Array.from(m.host.querySelectorAll('tr')).find((tr) => tr.textContent?.includes('Quarterly plan'));
    await m.click(row as Element);
    await m.flush();
    expect(state.seen).toContain('/api/workspaces/ws-e/analytics/chats/conv-1');
    expect(m.host.textContent).toContain('Conversation has no stored messages');
    expect(button(m, 'Copy')).not.toBeNull();
  });

  it('filters by an in-scope member, keyed by user_id', async () => {
    state.access['/api/workspaces/ws-f/analytics/access'] = { can_read: true };
    const m = await render({ kind: 'workspace', workspaceId: 'ws-f' });
    await m.click(button(m, 'All users'));
    await m.click(buttons(m).find((b) => b.textContent?.endsWith('ann@acme.test')) ?? null);
    await until(m, () => (m.host.textContent ?? '').includes('Event history'));
    expect(state.seen).toContain('/api/workspaces/ws-f/analytics/users/u-ann?period=today&user_id=u-ann');
    // One user's view: Overview (their detail), Chats and Events only.
    expect(button(m, 'Users')).toBeNull();
    expect(button(m, 'Sessions')).toBeNull();
    expect(m.host.textContent).toContain('Event history');
  });
});
