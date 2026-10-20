import { describe, expect, it } from 'vitest';
import {
  isSlidesDeckResult,
  slidesDeckCardFromToolCalls,
  slidesDeckHref,
  slidesDeckTitleFromToolOutput,
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

const PUBLISHED_OUTPUT = JSON.stringify({
  ok: true,
  nexus_shipped: true,
  slug: 'palantir',
  title: 'Palantir',
  workspace_id: 'ws-1',
});

describe('isSlidesDeckResult', () => {
  it('accepts create-style results with slug (no nexus_shipped)', () => {
    expect(isSlidesDeckResult(JSON.parse(CREATED_OUTPUT))).toBe(true);
  });

  it('accepts publish-style results only when ok and nexus_shipped', () => {
    expect(isSlidesDeckResult(JSON.parse(PUBLISHED_OUTPUT))).toBe(true);
    expect(
      isSlidesDeckResult({
        ok: true,
        nexus_shipped: false,
        slug: 'x',
        title: 'X',
      }),
    ).toBe(false);
    expect(isSlidesDeckResult({ nexus_shipped: true, slug: 'x', title: 'X' })).toBe(
      false,
    );
  });

  it('rejects missing slug or error payloads', () => {
    expect(isSlidesDeckResult({ title: 'X' })).toBe(false);
    expect(isSlidesDeckResult({ slug: 'x', error: 'nope' })).toBe(false);
  });
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

  it('uses name when title is absent', () => {
    const output = JSON.stringify({
      slug: 'brief-deck',
      name: 'Brief Deck',
      workspace_id: 'ws-1',
    });
    expect(slidesDeckCardFromToolCalls([toolCall({ output })])?.title).toBe('Brief Deck');
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

  it('derives a deck card from a generic publish_deck result shape', () => {
    expect(
      slidesDeckCardFromToolCalls([
        toolCall({
          rawName: 'publish_deck',
          toolName: 'Publish Deck',
          output: PUBLISHED_OUTPUT,
        }),
      ]),
    ).toEqual({
      slug: 'palantir',
      title: 'Palantir',
      workspaceId: 'ws-1',
    });
  });

  it('ignores publish-style results unless ok and nexus_shipped are both true', () => {
    expect(
      slidesDeckCardFromToolCalls([
        toolCall({
          rawName: 'publish_deck',
          output: JSON.stringify({
            ok: false,
            nexus_shipped: false,
            slug: 'nissan-brief',
            title: 'Nissan Brief',
            workspace_id: 'ws-1',
          }),
        }),
      ]),
    ).toBeNull();
    expect(
      slidesDeckCardFromToolCalls([
        toolCall({
          rawName: 'publish_deck',
          output: JSON.stringify({
            ok: true,
            nexus_shipped: false,
            slug: 'nissan-brief',
            workspace_id: 'ws-1',
          }),
        }),
      ]),
    ).toBeNull();
    expect(
      slidesDeckCardFromToolCalls([
        toolCall({
          rawName: 'publish_deck',
          output: JSON.stringify({
            slug: 'nissan-brief',
            nexus_shipped: true,
            workspace_id: 'ws-1',
          }),
        }),
      ]),
    ).toBeNull();
  });

  it('still cards a shipped publish regardless of product tool name', () => {
    // Downstream product tools (any name) keep working if they return the contract.
    expect(
      slidesDeckCardFromToolCalls([
        toolCall({
          rawName: 'create_slides_project',
          output: PUBLISHED_OUTPUT,
        }),
      ]),
    ).toEqual({
      slug: 'palantir',
      title: 'Palantir',
      workspaceId: 'ws-1',
    });
  });
});

describe('slidesDeckTitleFromToolOutput', () => {
  it('reads the title a slides tool result carries', () => {
    expect(slidesDeckTitleFromToolOutput(CREATED_OUTPUT)).toBe('Latest News About AI');
    expect(
      slidesDeckTitleFromToolOutput(
        JSON.stringify({ slug: 'materiaux-de-construction', title: 'Matériaux de construction' }),
      ),
    ).toBe('Matériaux de construction');
  });

  it('reads name when title is absent', () => {
    expect(
      slidesDeckTitleFromToolOutput(JSON.stringify({ slug: 'x', name: 'Named Deck' })),
    ).toBe('Named Deck');
  });

  it('returns nothing for output with no title', () => {
    expect(slidesDeckTitleFromToolOutput(undefined)).toBe('');
    expect(slidesDeckTitleFromToolOutput('wrote the deck')).toBe('');
    expect(slidesDeckTitleFromToolOutput(JSON.stringify({ slug: 'x' }))).toBe('');
    expect(
      slidesDeckTitleFromToolOutput(JSON.stringify({ title: 'X', error: 'nope' })),
    ).toBe('');
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
