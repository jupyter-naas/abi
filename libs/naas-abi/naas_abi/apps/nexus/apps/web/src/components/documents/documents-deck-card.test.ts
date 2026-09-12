import { describe, expect, it } from 'vitest';
import {
  sectionsDocumentCardFromToolCalls,
  sectionsDocumentHref,
  sectionsDocumentTitleFromToolOutput,
} from './documents-card';
import type { ToolCall } from '@/stores/workspace';

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

describe('sectionsDocumentCardFromToolCalls', () => {
  it('derives a document card after Abi creates a document from chat', () => {
    const card = sectionsDocumentCardFromToolCalls([toolCall({ output: CREATED_OUTPUT })]);
    expect(card).toEqual({
      slug: 'latest-news-about-ai',
      title: 'Latest News About AI',
      workspaceId: 'ws-1',
    });
  });

  it('returns null when no sections tool ran', () => {
    expect(sectionsDocumentCardFromToolCalls([])).toBeNull();
    expect(
      sectionsDocumentCardFromToolCalls([
        toolCall({ rawName: 'web_search', output: '{"results": []}' }),
      ]),
    ).toBeNull();
  });

  it('ignores a failed create', () => {
    const failed = JSON.stringify({ error: 'Forgejo is not reachable.' });
    expect(sectionsDocumentCardFromToolCalls([toolCall({ output: failed })])).toBeNull();
  });

  it('ignores a tool call that is still running', () => {
    expect(
      sectionsDocumentCardFromToolCalls([toolCall({ status: 'running', output: undefined })]),
    ).toBeNull();
  });

  it('tolerates plain text tool output', () => {
    expect(
      sectionsDocumentCardFromToolCalls([toolCall({ output: 'created the document' })]),
    ).toBeNull();
  });

  it('falls back to a readable title when the tool omits one', () => {
    const output = JSON.stringify({ slug: 'ai-news-roundup', workspace_id: 'ws-1' });
    expect(sectionsDocumentCardFromToolCalls([toolCall({ output })])?.title).toBe(
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
    expect(sectionsDocumentCardFromToolCalls([renamed])).toEqual({
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
    const card = sectionsDocumentCardFromToolCalls([
      toolCall({ output: CREATED_OUTPUT }),
      write,
    ]);
    expect(card?.slug).toBe('latest-news-about-ai');
    expect(card?.title).toBe('Latest News About AI');
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
      sectionsDocumentCardFromToolCalls([toolCall({ output: CREATED_OUTPUT }), second])?.slug,
    ).toBe('second-document');
  });
});

describe('sectionsDocumentTitleFromToolOutput', () => {
  it('reads the title a sections tool result carries', () => {
    expect(sectionsDocumentTitleFromToolOutput(CREATED_OUTPUT)).toBe('Latest News About AI');
    expect(
      sectionsDocumentTitleFromToolOutput(
        JSON.stringify({ slug: 'materiaux-de-construction', title: 'Matériaux de construction' }),
      ),
    ).toBe('Matériaux de construction');
  });

  it('returns nothing for output with no title', () => {
    expect(sectionsDocumentTitleFromToolOutput(undefined)).toBe('');
    expect(sectionsDocumentTitleFromToolOutput('wrote the document')).toBe('');
    expect(sectionsDocumentTitleFromToolOutput(JSON.stringify({ slug: 'x' }))).toBe('');
    expect(
      sectionsDocumentTitleFromToolOutput(JSON.stringify({ title: 'X', error: 'nope' })),
    ).toBe('');
  });
});

describe('sectionsDocumentHref', () => {
  it('links into the Documents surface for the document workspace', () => {
    expect(
      sectionsDocumentHref({ slug: 'ai', title: 'AI', workspaceId: 'ws-1' }, 'ws-current'),
    ).toBe('/workspace/ws-1/documents/ai');
  });

  it('falls back to the current workspace when the tool omitted one', () => {
    expect(
      sectionsDocumentHref({ slug: 'ai', title: 'AI', workspaceId: '' }, 'ws-current'),
    ).toBe('/workspace/ws-current/documents/ai');
  });

  it('encodes an unusual slug', () => {
    expect(
      sectionsDocumentHref({ slug: 'a b', title: 'AI', workspaceId: 'ws-1' }, 'ws-1'),
    ).toBe('/workspace/ws-1/documents/a%20b');
  });
});
