import { describe, expect, it } from 'vitest';
import {
  slidesDeckCardFromToolCalls,
  slidesDeckHref,
} from './slides-deck-card';
import type { ToolCall } from '@/stores/workspace';

function toolCall(partial: Partial<ToolCall>): ToolCall {
  return {
    id: 'tc-1',
    toolName: 'Create Slides Project',
    prefix: 'Tool',
    rawName: 'create_slides_project',
    status: 'done',
    ...partial,
  };
}

const CREATED_OUTPUT = JSON.stringify({
  ok: true,
  created: true,
  slug: 'latest-news-about-ai',
  title: 'Latest News About AI',
  branch: 'slides/ws-1/latest-news-about-ai',
  path: 'slides/ws-1/latest-news-about-ai/deck.html',
  workspace_id: 'ws-1',
});

describe('slidesDeckCardFromToolCalls', () => {
  it('derives a deck card after Abi creates a deck from chat', () => {
    const card = slidesDeckCardFromToolCalls([toolCall({ output: CREATED_OUTPUT })]);
    expect(card).toEqual({
      slug: 'latest-news-about-ai',
      title: 'Latest News About AI',
      workspaceId: 'ws-1',
    });
  });

  it('returns null when no slides tool ran', () => {
    expect(slidesDeckCardFromToolCalls([])).toBeNull();
    expect(
      slidesDeckCardFromToolCalls([
        toolCall({ rawName: 'web_search', output: '{"results": []}' }),
      ]),
    ).toBeNull();
  });

  it('ignores a failed create', () => {
    const failed = JSON.stringify({ error: 'Forgejo is not reachable.' });
    expect(slidesDeckCardFromToolCalls([toolCall({ output: failed })])).toBeNull();
  });

  it('ignores a tool call that is still running', () => {
    expect(
      slidesDeckCardFromToolCalls([toolCall({ status: 'running', output: undefined })]),
    ).toBeNull();
  });

  it('tolerates plain text tool output', () => {
    expect(
      slidesDeckCardFromToolCalls([toolCall({ output: 'created the deck' })]),
    ).toBeNull();
  });

  it('falls back to a readable title when the tool omits one', () => {
    const output = JSON.stringify({ slug: 'ai-news-roundup', workspace_id: 'ws-1' });
    expect(slidesDeckCardFromToolCalls([toolCall({ output })])?.title).toBe(
      'Ai News Roundup',
    );
  });

  it('prefers the created deck over a later write on the same deck', () => {
    const write = toolCall({
      id: 'tc-2',
      rawName: 'write_slides_section',
      output: JSON.stringify({ slug: 'latest-news-about-ai', workspace_id: 'ws-1' }),
    });
    const card = slidesDeckCardFromToolCalls([
      toolCall({ output: CREATED_OUTPUT }),
      write,
    ]);
    expect(card?.slug).toBe('latest-news-about-ai');
    expect(card?.title).toBe('Latest News About AI');
  });

  it('uses the most recent deck when chat creates more than one', () => {
    const second = toolCall({
      id: 'tc-2',
      output: JSON.stringify({
        created: true,
        slug: 'second-deck',
        title: 'Second Deck',
        workspace_id: 'ws-1',
      }),
    });
    expect(
      slidesDeckCardFromToolCalls([toolCall({ output: CREATED_OUTPUT }), second])?.slug,
    ).toBe('second-deck');
  });
});

describe('slidesDeckHref', () => {
  it('links into the Slides surface for the deck workspace', () => {
    expect(
      slidesDeckHref({ slug: 'ai', title: 'AI', workspaceId: 'ws-1' }, 'ws-current'),
    ).toBe('/workspace/ws-1/slides/ai');
  });

  it('falls back to the current workspace when the tool omitted one', () => {
    expect(
      slidesDeckHref({ slug: 'ai', title: 'AI', workspaceId: '' }, 'ws-current'),
    ).toBe('/workspace/ws-current/slides/ai');
  });

  it('encodes an unusual slug', () => {
    expect(
      slidesDeckHref({ slug: 'a b', title: 'AI', workspaceId: 'ws-1' }, 'ws-1'),
    ).toBe('/workspace/ws-1/slides/a%20b');
  });
});
