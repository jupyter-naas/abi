import { describe, expect, it } from 'vitest';
import type { ToolCall } from '@/stores/workspace';
import { OFFICE_CARD_RULES, officeCardFromToolCalls, officeCardHref, officeTitleFromToolOutput } from './office-card';

/*
 * Each kind recognises its own results: Documents and Sheets by write-tool name,
 * Slides by result shape. The assertions below are per kind on purpose.
 */

describe('documents cards', () => {
  function toolCall(partial: Partial<ToolCall>): ToolCall {
    return {
      id: 'tc-1',
      toolName: 'Create Documents Project',
      prefix: 'Tool',
      rawName: 'create_documents_project',
      status: 'done',
      ...partial,
    };
  }

  const CREATED_OUTPUT = JSON.stringify({
    ok: true,
    created: true,
    slug: 'latest-news-about-ai',
    title: 'Latest News About AI',
    branch: 'documents/ws-1/latest-news-about-ai',
    path: 'documents/ws-1/latest-news-about-ai/document.html',
    workspace_id: 'ws-1',
  });

  describe('officeCardFromToolCalls', () => {
    it('derives a document card after Abi creates a document from chat', () => {
      const card = officeCardFromToolCalls('documents', [toolCall({ output: CREATED_OUTPUT })]);
      expect(card).toEqual({
        slug: 'latest-news-about-ai',
        title: 'Latest News About AI',
        workspaceId: 'ws-1',
      });
    });

    it('returns null when no sections tool ran', () => {
      expect(officeCardFromToolCalls('documents', [])).toBeNull();
      expect(
        officeCardFromToolCalls('documents', [
          toolCall({ rawName: 'web_search', output: '{"results": []}' }),
        ]),
      ).toBeNull();
    });

    it('ignores a failed create', () => {
      const failed = JSON.stringify({ error: 'Forgejo is not reachable.' });
      expect(officeCardFromToolCalls('documents', [toolCall({ output: failed })])).toBeNull();
    });

    it('ignores a tool call that is still running', () => {
      expect(
        officeCardFromToolCalls('documents', [toolCall({ status: 'running', output: undefined })]),
      ).toBeNull();
    });

    it('tolerates plain text tool output', () => {
      expect(
        officeCardFromToolCalls('documents', [toolCall({ output: 'created the document' })]),
      ).toBeNull();
    });

    it('falls back to a readable title when the tool omits one', () => {
      const output = JSON.stringify({ slug: 'ai-news-roundup', workspace_id: 'ws-1' });
      expect(officeCardFromToolCalls('documents', [toolCall({ output })])?.title).toBe(
        'Ai News Roundup',
      );
    });

    it('picks up a rename_document title for the chat card', () => {
      const renamed = toolCall({
        rawName: 'rename_document',
        output: JSON.stringify({
          ok: true,
          slug: 'untitled-local',
          title: 'Forvis Mazars Story',
          workspace_id: 'ws-1',
        }),
      });
      expect(officeCardFromToolCalls('documents', [renamed])).toEqual({
        slug: 'untitled-local',
        title: 'Forvis Mazars Story',
        workspaceId: 'ws-1',
      });
    });

    it('prefers the created document over a later write on the same document', () => {
      const write = toolCall({
        id: 'tc-2',
        rawName: 'write_document_section',
        output: JSON.stringify({ slug: 'latest-news-about-ai', workspace_id: 'ws-1' }),
      });
      const card = officeCardFromToolCalls('documents', [
        toolCall({ output: CREATED_OUTPUT }),
        write,
      ]);
      expect(card?.slug).toBe('latest-news-about-ai');
      expect(card?.title).toBe('Latest News About AI');
    });

    it('derives a document card from fill_document_slots, including persisted labels', () => {
      const filled = JSON.stringify({
        ok: true,
        slug: 'strategie-ia-de-forvis-mazars',
        title: 'Stratégie IA de Forvis Mazars',
        path: 'documents/ws-1/strategie-ia-de-forvis-mazars/document.html',
      });
      expect(
        officeCardFromToolCalls('documents', [
          toolCall({ rawName: 'fill_document_slots', output: filled }),
        ]),
      ).toEqual({
        slug: 'strategie-ia-de-forvis-mazars',
        title: 'Stratégie IA de Forvis Mazars',
        workspaceId: '',
      });
      expect(
        officeCardFromToolCalls('documents', [
          toolCall({
            toolName: 'Fill Document Slots',
            rawName: 'Fill Document Slots',
            output: filled,
          }),
        ])?.slug,
      ).toBe('strategie-ia-de-forvis-mazars');
      expect(
        officeCardFromToolCalls('documents', [
          toolCall({
            toolName: 'Create Documents Project',
            rawName: 'Create Documents Project',
            output: CREATED_OUTPUT,
          }),
        ])?.slug,
      ).toBe('latest-news-about-ai');
    });

    it('uses the most recent document when chat creates more than one', () => {
      const second = toolCall({
        id: 'tc-2',
        output: JSON.stringify({
          created: true,
          slug: 'second-document',
          title: 'Second Document',
          workspace_id: 'ws-1',
        }),
      });
      expect(
        officeCardFromToolCalls('documents', [toolCall({ output: CREATED_OUTPUT }), second])?.slug,
      ).toBe('second-document');
    });
  });

  describe('officeTitleFromToolOutput', () => {
    it('reads the title a sections tool result carries', () => {
      expect(officeTitleFromToolOutput('documents', CREATED_OUTPUT)).toBe('Latest News About AI');
      expect(
        officeTitleFromToolOutput('documents', 
          JSON.stringify({ slug: 'materiaux-de-construction', title: 'Matériaux de construction' }),
        ),
      ).toBe('Matériaux de construction');
    });

    it('returns nothing for output with no title', () => {
      expect(officeTitleFromToolOutput('documents', undefined)).toBe('');
      expect(officeTitleFromToolOutput('documents', 'wrote the document')).toBe('');
      expect(officeTitleFromToolOutput('documents', JSON.stringify({ slug: 'x' }))).toBe('');
      expect(
        officeTitleFromToolOutput('documents', JSON.stringify({ title: 'X', error: 'nope' })),
      ).toBe('');
    });
  });

  describe('officeCardHref', () => {
    it('links into the Documents surface for the document workspace', () => {
      expect(
        officeCardHref('documents', { slug: 'ai', title: 'AI', workspaceId: 'ws-1' }, 'ws-current'),
      ).toBe('/workspace/ws-1/documents/ai');
    });

    it('falls back to the current workspace when the tool omitted one', () => {
      expect(
        officeCardHref('documents', { slug: 'ai', title: 'AI', workspaceId: '' }, 'ws-current'),
      ).toBe('/workspace/ws-current/documents/ai');
    });

    it('encodes an unusual slug', () => {
      expect(
        officeCardHref('documents', { slug: 'a b', title: 'AI', workspaceId: 'ws-1' }, 'ws-1'),
      ).toBe('/workspace/ws-1/documents/a%20b');
    });
  });
});

describe('sheets cards', () => {
  function toolCall(partial: Partial<ToolCall>): ToolCall {
    return {
      id: 'tc-1',
      toolName: 'Create Sheets Project',
      prefix: 'Tool',
      rawName: 'create_sheets_project',
      status: 'done',
      ...partial,
    };
  }

  const CREATED_OUTPUT = JSON.stringify({
    ok: true,
    created: true,
    slug: 'latest-news-about-ai',
    title: 'Latest News About AI',
    branch: 'sheets/ws-1/latest-news-about-ai',
    path: 'sheets/ws-1/latest-news-about-ai/workbook.html',
    workspace_id: 'ws-1',
  });

  describe('officeCardFromToolCalls', () => {
    it('derives a workbook card after Abi creates a workbook from chat', () => {
      const card = officeCardFromToolCalls('sheets', [toolCall({ output: CREATED_OUTPUT })]);
      expect(card).toEqual({
        slug: 'latest-news-about-ai',
        title: 'Latest News About AI',
        workspaceId: 'ws-1',
      });
    });

    it('returns null when no sheets tool ran', () => {
      expect(officeCardFromToolCalls('sheets', [])).toBeNull();
      expect(
        officeCardFromToolCalls('sheets', [
          toolCall({ rawName: 'web_search', output: '{"results": []}' }),
        ]),
      ).toBeNull();
    });

    it('ignores a failed create', () => {
      const failed = JSON.stringify({ error: 'Forgejo is not reachable.' });
      expect(officeCardFromToolCalls('sheets', [toolCall({ output: failed })])).toBeNull();
    });

    it('ignores a tool call that is still running', () => {
      expect(
        officeCardFromToolCalls('sheets', [toolCall({ status: 'running', output: undefined })]),
      ).toBeNull();
    });

    it('tolerates plain text tool output', () => {
      expect(
        officeCardFromToolCalls('sheets', [toolCall({ output: 'created the workbook' })]),
      ).toBeNull();
    });

    it('falls back to a readable title when the tool omits one', () => {
      const output = JSON.stringify({ slug: 'ai-news-roundup', workspace_id: 'ws-1' });
      expect(officeCardFromToolCalls('sheets', [toolCall({ output })])?.title).toBe(
        'Ai News Roundup',
      );
    });

    it('prefers the created workbook over a later write on the same workbook', () => {
      const write = toolCall({
        id: 'tc-2',
        rawName: 'write_sheets_section',
        output: JSON.stringify({ slug: 'latest-news-about-ai', workspace_id: 'ws-1' }),
      });
      const card = officeCardFromToolCalls('sheets', [
        toolCall({ output: CREATED_OUTPUT }),
        write,
      ]);
      expect(card?.slug).toBe('latest-news-about-ai');
      expect(card?.title).toBe('Latest News About AI');
    });

    it('uses the most recent workbook when chat creates more than one', () => {
      const second = toolCall({
        id: 'tc-2',
        output: JSON.stringify({
          created: true,
          slug: 'second-workbook',
          title: 'Second Workbook',
          workspace_id: 'ws-1',
        }),
      });
      expect(
        officeCardFromToolCalls('sheets', [toolCall({ output: CREATED_OUTPUT }), second])?.slug,
      ).toBe('second-workbook');
    });
  });

  describe('officeTitleFromToolOutput', () => {
    it('reads the title a sheets tool result carries', () => {
      expect(officeTitleFromToolOutput('sheets', CREATED_OUTPUT)).toBe('Latest News About AI');
      expect(
        officeTitleFromToolOutput('sheets', 
          JSON.stringify({ slug: 'materiaux-de-construction', title: 'Matériaux de construction' }),
        ),
      ).toBe('Matériaux de construction');
    });

    it('returns nothing for output with no title', () => {
      expect(officeTitleFromToolOutput('sheets', undefined)).toBe('');
      expect(officeTitleFromToolOutput('sheets', 'wrote the workbook')).toBe('');
      expect(officeTitleFromToolOutput('sheets', JSON.stringify({ slug: 'x' }))).toBe('');
      expect(
        officeTitleFromToolOutput('sheets', JSON.stringify({ title: 'X', error: 'nope' })),
      ).toBe('');
    });
  });

  describe('officeCardHref', () => {
    it('links into the Sheets surface for the workbook workspace', () => {
      expect(
        officeCardHref('sheets', { slug: 'ai', title: 'AI', workspaceId: 'ws-1' }, 'ws-current'),
      ).toBe('/workspace/ws-1/sheets/ai');
    });

    it('falls back to the current workspace when the tool omitted one', () => {
      expect(
        officeCardHref('sheets', { slug: 'ai', title: 'AI', workspaceId: '' }, 'ws-current'),
      ).toBe('/workspace/ws-current/sheets/ai');
    });

    it('encodes an unusual slug', () => {
      expect(
        officeCardHref('sheets', { slug: 'a b', title: 'AI', workspaceId: 'ws-1' }, 'ws-1'),
      ).toBe('/workspace/ws-1/sheets/a%20b');
    });
  });
});

describe('slides cards', () => {
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

  describe('slides result shape', () => {
    it('accepts create-style results with slug (no nexus_shipped)', () => {
      expect(OFFICE_CARD_RULES.slides.accepts(JSON.parse(CREATED_OUTPUT))).toBe(true);
    });

    it('accepts publish-style results only when ok and nexus_shipped', () => {
      expect(OFFICE_CARD_RULES.slides.accepts(JSON.parse(PUBLISHED_OUTPUT))).toBe(true);
      expect(
        OFFICE_CARD_RULES.slides.accepts({
          ok: true,
          nexus_shipped: false,
          slug: 'x',
          title: 'X',
        }),
      ).toBe(false);
      expect(OFFICE_CARD_RULES.slides.accepts({ nexus_shipped: true, slug: 'x', title: 'X' })).toBe(
        false,
      );
    });

    it('rejects missing slug or error payloads', () => {
      expect(OFFICE_CARD_RULES.slides.accepts({ title: 'X' })).toBe(false);
      expect(OFFICE_CARD_RULES.slides.accepts({ slug: 'x', error: 'nope' })).toBe(false);
    });
  });

  describe('officeCardFromToolCalls', () => {
    it('derives a deck card after Abi creates a deck from chat', () => {
      const card = officeCardFromToolCalls('slides', [toolCall({ output: CREATED_OUTPUT })]);
      expect(card).toEqual({
        slug: 'latest-news-about-ai',
        title: 'Latest News About AI',
        workspaceId: 'ws-1',
      });
    });

    it('returns null when no slides tool ran', () => {
      expect(officeCardFromToolCalls('slides', [])).toBeNull();
      expect(
        officeCardFromToolCalls('slides', [
          toolCall({ rawName: 'web_search', output: '{"results": []}' }),
        ]),
      ).toBeNull();
    });

    it('ignores a failed create', () => {
      const failed = JSON.stringify({ error: 'Forgejo is not reachable.' });
      expect(officeCardFromToolCalls('slides', [toolCall({ output: failed })])).toBeNull();
    });

    it('ignores a tool call that is still running', () => {
      expect(
        officeCardFromToolCalls('slides', [toolCall({ status: 'running', output: undefined })]),
      ).toBeNull();
    });

    it('tolerates plain text tool output', () => {
      expect(
        officeCardFromToolCalls('slides', [toolCall({ output: 'created the deck' })]),
      ).toBeNull();
    });

    it('falls back to a readable title when the tool omits one', () => {
      const output = JSON.stringify({ slug: 'ai-news-roundup', workspace_id: 'ws-1' });
      expect(officeCardFromToolCalls('slides', [toolCall({ output })])?.title).toBe(
        'Ai News Roundup',
      );
    });

    it('uses name when title is absent', () => {
      const output = JSON.stringify({
        slug: 'brief-deck',
        name: 'Brief Deck',
        workspace_id: 'ws-1',
      });
      expect(officeCardFromToolCalls('slides', [toolCall({ output })])?.title).toBe('Brief Deck');
    });

    it('prefers the created deck over a later write on the same deck', () => {
      const write = toolCall({
        id: 'tc-2',
        rawName: 'write_slides_section',
        output: JSON.stringify({ slug: 'latest-news-about-ai', workspace_id: 'ws-1' }),
      });
      const card = officeCardFromToolCalls('slides', [
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
        officeCardFromToolCalls('slides', [toolCall({ output: CREATED_OUTPUT }), second])?.slug,
      ).toBe('second-deck');
    });

    it('derives a deck card from a generic publish_deck result shape', () => {
      expect(
        officeCardFromToolCalls('slides', [
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
        officeCardFromToolCalls('slides', [
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
        officeCardFromToolCalls('slides', [
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
        officeCardFromToolCalls('slides', [
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
        officeCardFromToolCalls('slides', [
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

  describe('officeTitleFromToolOutput', () => {
    it('reads the title a slides tool result carries', () => {
      expect(officeTitleFromToolOutput('slides', CREATED_OUTPUT)).toBe('Latest News About AI');
      expect(
        officeTitleFromToolOutput('slides', 
          JSON.stringify({ slug: 'materiaux-de-construction', title: 'Matériaux de construction' }),
        ),
      ).toBe('Matériaux de construction');
    });

    it('reads name when title is absent', () => {
      expect(
        officeTitleFromToolOutput('slides', JSON.stringify({ slug: 'x', name: 'Named Deck' })),
      ).toBe('Named Deck');
    });

    it('returns nothing for output with no title', () => {
      expect(officeTitleFromToolOutput('slides', undefined)).toBe('');
      expect(officeTitleFromToolOutput('slides', 'wrote the deck')).toBe('');
      expect(officeTitleFromToolOutput('slides', JSON.stringify({ slug: 'x' }))).toBe('');
      expect(
        officeTitleFromToolOutput('slides', JSON.stringify({ title: 'X', error: 'nope' })),
      ).toBe('');
    });
  });

  describe('officeCardHref', () => {
    it('links into the Slides surface for the deck workspace', () => {
      expect(
        officeCardHref('slides', { slug: 'ai', title: 'AI', workspaceId: 'ws-1' }, 'ws-current'),
      ).toBe('/workspace/ws-1/slides/ai');
    });

    it('falls back to the current workspace when the tool omitted one', () => {
      expect(
        officeCardHref('slides', { slug: 'ai', title: 'AI', workspaceId: '' }, 'ws-current'),
      ).toBe('/workspace/ws-current/slides/ai');
    });

    it('encodes an unusual slug', () => {
      expect(
        officeCardHref('slides', { slug: 'a b', title: 'AI', workspaceId: 'ws-1' }, 'ws-1'),
      ).toBe('/workspace/ws-1/slides/a%20b');
    });
  });
});
