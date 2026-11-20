import { describe, expect, it } from 'vitest';
import { analyticsTabs, shownTab } from './tabs';

const org = { kind: 'organization', orgId: 'org-1' } as const;
const ws = { kind: 'workspace', workspaceId: 'ws-1' } as const;
const keys = (tabs: { key: string }[]) => tabs.map((t) => t.key);

describe('analytics tabs', () => {
  it('shows the Workspaces tab in an organization only', () => {
    expect(keys(analyticsTabs(org))).toEqual(['overview', 'users', 'sessions', 'pages', 'workspaces', 'chats', 'events']);
    expect(keys(analyticsTabs(ws))).toEqual(['overview', 'users', 'sessions', 'pages', 'chats', 'events']);
  });

  it('keeps Overview, Chats and Events for one user', () => {
    expect(keys(analyticsTabs(org, { userSelected: true }))).toEqual(['overview', 'chats', 'events']);
    expect(keys(analyticsTabs(ws, { userSelected: true }))).toEqual(['overview', 'chats', 'events']);
  });

  it('falls back to Overview when the tab is not offered', () => {
    expect(shownTab('workspaces', analyticsTabs(ws))).toBe('overview');
    expect(shownTab('sessions', analyticsTabs(org, { userSelected: true }))).toBe('overview');
    expect(shownTab('chats', analyticsTabs(org, { userSelected: true }))).toBe('chats');
  });
});
