import { describe, expect, it } from 'vitest';

import {
  buildQuickOpenItems,
  conversationUpdatedAtMs,
  filterQuickOpenItems,
  groupQuickOpenItems,
  scoreQuickOpen,
  type QuickOpenItem,
} from './quick-open';

const item = (
  id: string,
  group: QuickOpenItem['group'],
  label: string,
  hint?: string,
): QuickOpenItem => ({
  id,
  group,
  label,
  hint,
  action: { kind: 'href', href: `/${id}` },
});

const catalog = [
  item('home', 'navigate', 'Home'),
  item('chat', 'navigate', 'Chat'),
  item('acme', 'workspace', 'Acme'),
  item('core', 'workspace', 'Core Team'),
  item('proposal', 'app', 'Acme Portal'),
  item('thread', 'chat', 'Q1 review', 'yesterday'),
];

describe('scoreQuickOpen', () => {
  it('scores an exact label highest', () => {
    expect(scoreQuickOpen(catalog[1], 'chat')).toBe(3);
    expect(scoreQuickOpen(catalog[1], 'cha')).toBe(2);
    expect(scoreQuickOpen(catalog[1], 'at')).toBe(1);
  });

  it('matches the hint when the label does not', () => {
    expect(scoreQuickOpen(catalog[5], 'yesterday')).toBe(1);
  });

  it('returns 0 when nothing matches', () => {
    expect(scoreQuickOpen(catalog[0], 'xyz')).toBe(0);
  });
});

describe('filterQuickOpenItems', () => {
  it('returns the catalog when the query is empty', () => {
    expect(filterQuickOpenItems(catalog, '  ').map((row) => row.id)).toEqual(
      catalog.map((row) => row.id),
    );
  });

  it('keeps group order and prefers a prefix match inside a group', () => {
    const rows = filterQuickOpenItems(
      [item('team', 'workspace', 'Team Space'), item('acme', 'workspace', 'Acme')],
      'a',
    );
    expect(rows.map((row) => row.id)).toEqual(['acme', 'team']);
  });

  it('is case-insensitive', () => {
    expect(filterQuickOpenItems(catalog, 'ACME').map((row) => row.id)).toEqual([
      'acme',
      'proposal',
    ]);
  });
});

describe('groupQuickOpenItems', () => {
  it('drops empty groups and keeps canonical order', () => {
    expect(groupQuickOpenItems(catalog).map((entry) => entry.group)).toEqual([
      'navigate',
      'workspace',
      'app',
      'chat',
    ]);
  });
});

describe('conversationUpdatedAtMs', () => {
  it('reads a Date', () => {
    expect(conversationUpdatedAtMs(new Date('2026-03-15T12:00:00.000Z'))).toBe(
      Date.parse('2026-03-15T12:00:00.000Z'),
    );
  });

  it('reads an ISO string from persist rehydrate', () => {
    expect(conversationUpdatedAtMs('2026-03-15T12:00:00.000Z')).toBe(
      Date.parse('2026-03-15T12:00:00.000Z'),
    );
  });

  it('reads a numeric timestamp', () => {
    expect(conversationUpdatedAtMs(1_710_000_000_000)).toBe(1_710_000_000_000);
  });

  it('returns 0 for null, undefined, and invalid values', () => {
    expect(conversationUpdatedAtMs(null)).toBe(0);
    expect(conversationUpdatedAtMs(undefined)).toBe(0);
    expect(conversationUpdatedAtMs('')).toBe(0);
    expect(conversationUpdatedAtMs('not-a-date')).toBe(0);
  });
});

describe('buildQuickOpenItems', () => {
  it('builds hrefs and workspace actions from a catalog', () => {
    const items = buildQuickOpenItems({
      workspaceId: 'ws-1',
      workspaces: [{ id: 'ws-1', name: 'Acme' }],
      sections: [{ id: 'home', label: 'Home', href: '/workspace/ws-1/home' }],
      apps: [{ id: 'acme-portal', name: 'Acme Portal' }],
      chats: [{ id: 'c1', title: 'Kickoff' }],
      files: [{ source: 'my-drive', path: 'notes.md', name: 'notes.md', type: 'file' }],
    });
    expect(items.map((row) => row.id)).toEqual([
      'nav:home',
      'ws:ws-1',
      'app:acme-portal',
      'chat:c1',
      'file:my-drive:notes.md',
    ]);
    expect(items[0].action).toEqual({
      kind: 'href',
      href: '/workspace/ws-1/home',
      panel: null,
    });
    expect(items[1].hint).toBe('Current');
    expect(items[2].action).toEqual({
      kind: 'href',
      href: '/workspace/ws-1/apps?open=acme-portal',
      panel: 'apps',
    });
  });
});
