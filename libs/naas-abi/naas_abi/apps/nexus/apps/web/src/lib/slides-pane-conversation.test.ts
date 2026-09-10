import { describe, expect, it } from 'vitest';

import type { Conversation } from '@/stores/workspace';

import {
  conversationMatchesSlidesSlug,
  dropSlidesPaneConversationKeys,
  findSlidesPaneConversationId,
  slidesDeckConversationPath,
  slidesOpenDeckBranch,
  slidesOpenDeckPath,
  slidesPaneConversationKey,
} from './slides-pane-conversation';

function conv(over: Partial<Conversation> & Pick<Conversation, 'id'>): Conversation {
  return {
    workspaceId: 'ws-1',
    title: 'New Conversation',
    messages: [],
    agent: 'slides',
    createdAt: new Date('2026-01-01'),
    updatedAt: new Date('2026-01-02'),
    ...over,
  };
}

describe('slidesPaneConversationKey', () => {
  it('scopes the binding by workspace and slug', () => {
    expect(slidesPaneConversationKey('ws-1', 'deck-a')).toBe('ws-1::deck-a');
  });
});

describe('slidesDeckConversationPath', () => {
  it('matches the pane Editing path', () => {
    expect(slidesDeckConversationPath('materiaux')).toBe('slides/materiaux/deck.html');
  });
});

describe('slidesOpenDeckPath', () => {
  it('namespaces the sidecar path with the workspace id', () => {
    expect(slidesOpenDeckPath('ws-894202a3986f', 'untitled-mtsg9zse')).toBe(
      'slides/ws-894202a3986f/untitled-mtsg9zse/deck.html',
    );
  });

  it('falls back to the legacy unscoped path without a workspace', () => {
    expect(slidesOpenDeckPath('', 'untitled-mtsg9zse')).toBe(
      'slides/untitled-mtsg9zse/deck.html',
    );
  });
});

describe('slidesOpenDeckBranch', () => {
  it('namespaces the branch with the workspace id', () => {
    expect(slidesOpenDeckBranch('ws-1', 'q3-br')).toBe('slides/ws-1/q3-br');
  });
});

describe('conversationMatchesSlidesSlug', () => {
  it('matches a stamped slidesSlug', () => {
    expect(conversationMatchesSlidesSlug(conv({ id: 'c1', slidesSlug: 'deck-a' }), 'deck-a')).toBe(
      true,
    );
    expect(conversationMatchesSlidesSlug(conv({ id: 'c1', slidesSlug: 'deck-a' }), 'deck-b')).toBe(
      false,
    );
  });

  it('matches an Editing-style path in the title or a message', () => {
    expect(
      conversationMatchesSlidesSlug(
        conv({ id: 'c1', title: 'Editing slides/deck-a/deck.html' }),
        'deck-a',
      ),
    ).toBe(true);
    expect(
      conversationMatchesSlidesSlug(
        conv({
          id: 'c1',
          messages: [{ content: 'Rewrite slides/deck-a/deck.html' }],
        }),
        'deck-a',
      ),
    ).toBe(true);
  });

  it('matches a non-generic deck title and ignores Untitled', () => {
    expect(
      conversationMatchesSlidesSlug(
        conv({ id: 'c1', title: 'Q3 materials brief' }),
        'deck-a',
        'Q3 materials brief',
      ),
    ).toBe(true);
    expect(
      conversationMatchesSlidesSlug(
        conv({ id: 'c1', title: 'Untitled presentation' }),
        'deck-a',
        'Untitled presentation',
      ),
    ).toBe(false);
  });
});

describe('findSlidesPaneConversationId', () => {
  it('prefers the stored binding when that thread still exists', () => {
    const conversations = [
      conv({ id: 'old', slidesSlug: 'deck-a', updatedAt: new Date('2026-02-01') }),
      conv({ id: 'bound', title: 'Other', updatedAt: new Date('2026-01-01') }),
    ];
    expect(
      findSlidesPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'deck-a',
        conversations,
        boundId: 'bound',
      }),
    ).toBe('bound');
  });

  it('ignores a stored id that is gone and falls back to the newest match', () => {
    const conversations = [
      conv({ id: 'older', slidesSlug: 'deck-a', updatedAt: new Date('2026-01-01') }),
      conv({ id: 'newer', slidesSlug: 'deck-a', updatedAt: new Date('2026-03-01') }),
    ];
    expect(
      findSlidesPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'deck-a',
        conversations,
        boundId: 'deleted',
      }),
    ).toBe('newer');
  });

  it('does not reuse another deck thread or another workspace', () => {
    expect(
      findSlidesPaneConversationId({
        workspaceId: 'ws-1',
        slug: 'deck-b',
        conversations: [
          conv({ id: 'a', slidesSlug: 'deck-a' }),
          conv({ id: 'other-ws', workspaceId: 'ws-2', slidesSlug: 'deck-b' }),
        ],
      }),
    ).toBeNull();
  });
});

describe('dropSlidesPaneConversationKeys', () => {
  it('removes every slug that pointed at the deleted thread', () => {
    expect(
      dropSlidesPaneConversationKeys(
        { 'ws-1::deck-a': 'conv-1', 'ws-1::deck-b': 'conv-2' },
        'conv-1',
      ),
    ).toEqual({ 'ws-1::deck-b': 'conv-2' });
  });
});
