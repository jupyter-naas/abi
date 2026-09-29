import { describe, expect, it } from 'vitest';

import type { Conversation } from '@/stores/workspace';

import {
  conversationMatchesSheetsSlug,
  dropSheetsPaneConversationKeys,
  findSheetsPaneConversationId,
  sheetsWorkbookConversationPath,
  sheetsOpenWorkbookBranch,
  sheetsOpenWorkbookPath,
  sheetsPaneConversationKey,
} from './sheets-pane-conversation';

function conv(over: Partial<Conversation> & Pick<Conversation, 'id'>): Conversation {
  return {
    workspaceId: 'ws-1',
    title: 'New Conversation',
    messages: [],
    agent: 'sheets',
    createdAt: new Date('2026-01-01'),
    updatedAt: new Date('2026-01-02'),
    ...over,
  };
}

describe('sheetsPaneConversationKey', () => {
  it('scopes the binding by workspace and slug', () => {
    expect(sheetsPaneConversationKey('ws-1', 'workbook-a')).toBe('ws-1::workbook-a');
  });
});

describe('sheetsWorkbookConversationPath', () => {
  it('matches the pane Editing path', () => {
    expect(sheetsWorkbookConversationPath('materiaux')).toBe('sheets/materiaux/workbook.html');
  });
});

describe('sheetsOpenWorkbookPath', () => {
  it('namespaces the sidecar path with the workspace id', () => {
    expect(sheetsOpenWorkbookPath('ws-894202a3986f', 'untitled-mtsg9zse')).toBe(
      'sheets/ws-894202a3986f/untitled-mtsg9zse/workbook.html',
    );
  });

  it('falls back to the legacy unscoped path without a workspace', () => {
    expect(sheetsOpenWorkbookPath('', 'untitled-mtsg9zse')).toBe(
      'sheets/untitled-mtsg9zse/workbook.html',
    );
  });
});

describe('sheetsOpenWorkbookBranch', () => {
  it('namespaces the branch with the workspace id', () => {
    expect(sheetsOpenWorkbookBranch('ws-1', 'q3-br')).toBe('sheets/ws-1/q3-br');
  });
});

describe('conversationMatchesSheetsSlug', () => {
  it('matches a stamped sheetsSlug', () => {
    expect(conversationMatchesSheetsSlug(conv({ id: 'c1', sheetsSlug: 'workbook-a' }), 'workbook-a')).toBe(
      true,
    );
    expect(conversationMatchesSheetsSlug(conv({ id: 'c1', sheetsSlug: 'workbook-a' }), 'workbook-b')).toBe(
      false,
    );
  });

  it('matches an Editing-style path in the title or a message', () => {
    expect(
      conversationMatchesSheetsSlug(
        conv({ id: 'c1', title: 'Editing sheets/workbook-a/workbook.html' }),
        'workbook-a',
      ),
    ).toBe(true);
    expect(
      conversationMatchesSheetsSlug(
        conv({
          id: 'c1',
          messages: [{ content: 'Rewrite sheets/workbook-a/workbook.html' }],
        }),
        'workbook-a',
      ),
    ).toBe(true);
  });

  it('matches a non-generic workbook title and ignores Untitled', () => {
    expect(
      conversationMatchesSheetsSlug(
        conv({ id: 'c1', title: 'Q3 materials brief' }),
        'workbook-a',
        'Q3 materials brief',
      ),
    ).toBe(true);
    expect(
      conversationMatchesSheetsSlug(
        conv({ id: 'c1', title: 'Untitled workbook' }),
        'workbook-a',
        'Untitled workbook',
      ),
    ).toBe(false);
  });
});

describe('findSheetsPaneConversationId', () => {
  it('prefers the stored binding when that thread still exists', () => {
    const conversations = [
      conv({ id: 'old', sheetsSlug: 'workbook-a', updatedAt: new Date('2026-02-01') }),
      conv({ id: 'bound', title: 'Other', updatedAt: new Date('2026-01-01') }),
    ];
    expect(
      findSheetsPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'workbook-a',
        conversations,
        boundId: 'bound',
      }),
    ).toBe('bound');
  });

  it('ignores a stored id that is gone and falls back to the newest match', () => {
    const conversations = [
      conv({ id: 'older', sheetsSlug: 'workbook-a', updatedAt: new Date('2026-01-01') }),
      conv({ id: 'newer', sheetsSlug: 'workbook-a', updatedAt: new Date('2026-03-01') }),
    ];
    expect(
      findSheetsPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'workbook-a',
        conversations,
        boundId: 'deleted',
      }),
    ).toBe('newer');
  });

  it('does not reuse another workbook thread or another workspace', () => {
    expect(
      findSheetsPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'workbook-b',
        conversations: [
          conv({ id: 'a', sheetsSlug: 'workbook-a' }),
          conv({ id: 'other-ws', workspaceId: 'ws-2', sheetsSlug: 'workbook-b' }),
        ],
      }),
    ).toBeNull();
  });
});

describe('dropSheetsPaneConversationKeys', () => {
  it('removes every slug that pointed at the deleted thread', () => {
    expect(
      dropSheetsPaneConversationKeys(
        { 'ws-1::workbook-a': 'conv-1', 'ws-1::workbook-b': 'conv-2' },
        'conv-1',
      ),
    ).toEqual({ 'ws-1::workbook-b': 'conv-2' });
  });
});
