import { describe, expect, it } from 'vitest';

import { newChatPath, nextChatUrl, parseChatRoute } from './chat-route';

const WS = 'ws-1';
const BASE = `/workspace/${WS}/chat`;

describe('parseChatRoute', () => {
  it('shows the conversation list on the bare chat route', () => {
    // The cold-start regression: a conversation id restored from localStorage
    // used to force the thread open here, so reopening the app dropped the user
    // into their last conversation instead of the list.
    expect(parseChatRoute(BASE)).toEqual({
      isChatRoute: true,
      conversationId: null,
      isThread: false,
    });
  });

  it('opens a thread for a conversation id', () => {
    expect(parseChatRoute(`${BASE}/conv-42`)).toEqual({
      isChatRoute: true,
      conversationId: 'conv-42',
      isThread: true,
    });
  });

  it('opens a blank thread on /chat/new without inventing a conversation id', () => {
    expect(parseChatRoute(`${BASE}/new`)).toEqual({
      isChatRoute: true,
      conversationId: null,
      isThread: true,
    });
  });

  it('ignores a trailing slash', () => {
    expect(parseChatRoute(`${BASE}/`).isThread).toBe(false);
    expect(parseChatRoute(`${BASE}/conv-42/`).conversationId).toBe('conv-42');
  });

  it('stops at a query string or fragment', () => {
    expect(parseChatRoute(`${BASE}/conv-42?ref=email`).conversationId).toBe('conv-42');
    expect(parseChatRoute(`${BASE}/conv-42#top`).conversationId).toBe('conv-42');
  });

  it('does not claim routes that merely start with the word chat', () => {
    // The old check was pathname.includes('/chat'), which would have swallowed these.
    expect(parseChatRoute(`/workspace/${WS}/chatbots`).isChatRoute).toBe(false);
    expect(parseChatRoute(`/workspace/${WS}/files`).isChatRoute).toBe(false);
  });

  it('treats a missing pathname as no route at all', () => {
    expect(parseChatRoute(null).isChatRoute).toBe(false);
    expect(parseChatRoute(undefined).isChatRoute).toBe(false);
  });
});

describe('newChatPath', () => {
  it('points at the blank thread inside the workspace', () => {
    expect(newChatPath(WS)).toBe(`${BASE}/new`);
  });

  it('degrades to a workspace-less path before a workspace is known', () => {
    expect(newChatPath(null)).toBe('/chat/new');
  });
});

describe('nextChatUrl', () => {
  it('leaves /chat/new alone while the thread is still blank', () => {
    // The regression this whole route contract exists for: rewriting to /chat
    // here sends the mobile shell straight back to the conversation list, so
    // the composer the user just opened disappears under them.
    expect(nextChatUrl(`${BASE}/new`, WS, null)).toBeNull();
  });

  it('promotes /chat/new to the real conversation once the first message lands', () => {
    expect(nextChatUrl(`${BASE}/new`, WS, 'conv-42')).toBe(`${BASE}/conv-42`);
  });

  it('adds the conversation id so the thread is shareable', () => {
    expect(nextChatUrl(BASE, WS, 'conv-42')).toBe(`${BASE}/conv-42`);
  });

  it('drops a stale conversation id when the chat is cleared', () => {
    expect(nextChatUrl(`${BASE}/conv-42`, WS, null)).toBe(BASE);
  });

  it('stays quiet when the URL already matches', () => {
    expect(nextChatUrl(`${BASE}/conv-42`, WS, 'conv-42')).toBeNull();
    expect(nextChatUrl(BASE, WS, null)).toBeNull();
  });

  it('keeps out of the way mid-workspace-switch', () => {
    // A router.push to another workspace is in flight; rewriting the URL to this
    // workspace's chat route would revert that navigation.
    expect(nextChatUrl('/workspace/ws-2/chat/conv-9', WS, 'conv-42')).toBeNull();
    expect(nextChatUrl(`/workspace/${WS}/files`, WS, 'conv-42')).toBeNull();
  });

  it('waits for a workspace and a pathname before rewriting anything', () => {
    expect(nextChatUrl(BASE, null, 'conv-42')).toBeNull();
    expect(nextChatUrl(null, WS, 'conv-42')).toBeNull();
  });
});
