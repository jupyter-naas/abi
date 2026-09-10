import { describe, expect, it } from 'vitest';

import type { Conversation } from '@/stores/workspace';

import {
  conversationMatchesDocumentSlug,
  dropDocumentsPaneConversationKeys,
  findDocumentsPaneConversationId,
  documentConversationPath,
  openDocumentBranch,
  openDocumentPath,
  documentsPaneConversationKey,
} from './documents-pane-conversation';

function conv(over: Partial<Conversation> & Pick<Conversation, 'id'>): Conversation {
  return {
    workspaceId: 'ws-1',
    title: 'New Conversation',
    messages: [],
    agent: 'documents',
    createdAt: new Date('2026-01-01'),
    updatedAt: new Date('2026-01-02'),
    ...over,
  };
}

describe('documentsPaneConversationKey', () => {
  it('scopes the binding by workspace and slug', () => {
    expect(documentsPaneConversationKey('ws-1', 'document-a')).toBe('ws-1::document-a');
  });
});

describe('documentConversationPath', () => {
  it('matches the pane Editing path', () => {
    expect(documentConversationPath('materiaux')).toBe('documents/materiaux/document.html');
  });
});

describe('openDocumentPath', () => {
  it('namespaces the sidecar path with the workspace id', () => {
    expect(openDocumentPath('ws-894202a3986f', 'untitled-mtsg9zse')).toBe(
      'documents/ws-894202a3986f/untitled-mtsg9zse/document.html',
    );
  });

  it('falls back to the legacy unscoped path without a workspace', () => {
    expect(openDocumentPath('', 'untitled-mtsg9zse')).toBe(
      'documents/untitled-mtsg9zse/document.html',
    );
  });
});

describe('openDocumentBranch', () => {
  it('namespaces the branch with the workspace id', () => {
    expect(openDocumentBranch('ws-1', 'q3-br')).toBe('documents/ws-1/q3-br');
  });
});

describe('conversationMatchesDocumentSlug', () => {
  it('matches a stamped sectionsSlug', () => {
    expect(conversationMatchesDocumentSlug(conv({ id: 'c1', sectionsSlug: 'document-a' }), 'document-a')).toBe(
      true,
    );
    expect(conversationMatchesDocumentSlug(conv({ id: 'c1', sectionsSlug: 'document-a' }), 'document-b')).toBe(
      false,
    );
  });

  it('matches an Editing-style path in the title or a message', () => {
    expect(
      conversationMatchesDocumentSlug(
        conv({ id: 'c1', title: 'Editing documents/document-a/document.html' }),
        'document-a',
      ),
    ).toBe(true);
    expect(
      conversationMatchesDocumentSlug(
        conv({
          id: 'c1',
          messages: [{ content: 'Rewrite documents/document-a/document.html' }],
        }),
        'document-a',
      ),
    ).toBe(true);
  });

  it('matches a non-generic document title and ignores Untitled', () => {
    expect(
      conversationMatchesDocumentSlug(
        conv({ id: 'c1', title: 'Q3 materials brief' }),
        'document-a',
        'Q3 materials brief',
      ),
    ).toBe(true);
    expect(
      conversationMatchesDocumentSlug(
        conv({ id: 'c1', title: 'Untitled document' }),
        'document-a',
        'Untitled document',
      ),
    ).toBe(false);
  });
});

describe('findDocumentsPaneConversationId', () => {
  it('prefers the stored binding when that thread still exists', () => {
    const conversations = [
      conv({ id: 'old', sectionsSlug: 'document-a', updatedAt: new Date('2026-02-01') }),
      conv({ id: 'bound', title: 'Other', updatedAt: new Date('2026-01-01') }),
    ];
    expect(
      findDocumentsPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'document-a',
        conversations,
        boundId: 'bound',
      }),
    ).toBe('bound');
  });

  it('ignores a stored id that is gone and falls back to the newest match', () => {
    const conversations = [
      conv({ id: 'older', sectionsSlug: 'document-a', updatedAt: new Date('2026-01-01') }),
      conv({ id: 'newer', sectionsSlug: 'document-a', updatedAt: new Date('2026-03-01') }),
    ];
    expect(
      findDocumentsPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'document-a',
        conversations,
        boundId: 'deleted',
      }),
    ).toBe('newer');
  });

  it('does not reuse another document thread or another workspace', () => {
    expect(
      findDocumentsPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'document-b',
        conversations: [
          conv({ id: 'a', sectionsSlug: 'document-a' }),
          conv({ id: 'other-ws', workspaceId: 'ws-2', sectionsSlug: 'document-b' }),
        ],
      }),
    ).toBeNull();
  });
});

describe('dropDocumentsPaneConversationKeys', () => {
  it('removes every slug that pointed at the deleted thread', () => {
    expect(
      dropDocumentsPaneConversationKeys(
        { 'ws-1::document-a': 'conv-1', 'ws-1::document-b': 'conv-2' },
        'conv-1',
      ),
    ).toEqual({ 'ws-1::document-b': 'conv-2' });
  });
});
