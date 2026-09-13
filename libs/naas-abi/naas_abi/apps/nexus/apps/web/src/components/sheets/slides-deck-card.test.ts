import { describe, expect, it } from 'vitest';
import {
  sheetsWorkbookCardFromToolCalls,
  sheetsWorkbookHref,
  sheetsWorkbookTitleFromToolOutput,
} from './sheets-workbook-card';
import type { ToolCall } from '@/stores/workspace';

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

describe('sheetsWorkbookCardFromToolCalls', () => {
  it('derives a workbook card after Abi creates a workbook from chat', () => {
    const card = sheetsWorkbookCardFromToolCalls([toolCall({ output: CREATED_OUTPUT })]);
    expect(card).toEqual({
      slug: 'latest-news-about-ai',
      title: 'Latest News About AI',
      workspaceId: 'ws-1',
    });
  });

  it('returns null when no sheets tool ran', () => {
    expect(sheetsWorkbookCardFromToolCalls([])).toBeNull();
    expect(
      sheetsWorkbookCardFromToolCalls([
        toolCall({ rawName: 'web_search', output: '{"results": []}' }),
      ]),
    ).toBeNull();
  });

  it('ignores a failed create', () => {
    const failed = JSON.stringify({ error: 'Forgejo is not reachable.' });
    expect(sheetsWorkbookCardFromToolCalls([toolCall({ output: failed })])).toBeNull();
  });

  it('ignores a tool call that is still running', () => {
    expect(
      sheetsWorkbookCardFromToolCalls([toolCall({ status: 'running', output: undefined })]),
    ).toBeNull();
  });

  it('tolerates plain text tool output', () => {
    expect(
      sheetsWorkbookCardFromToolCalls([toolCall({ output: 'created the workbook' })]),
    ).toBeNull();
  });

  it('falls back to a readable title when the tool omits one', () => {
    const output = JSON.stringify({ slug: 'ai-news-roundup', workspace_id: 'ws-1' });
    expect(sheetsWorkbookCardFromToolCalls([toolCall({ output })])?.title).toBe(
      'Ai News Roundup',
    );
  });

  it('prefers the created workbook over a later write on the same workbook', () => {
    const write = toolCall({
      id: 'tc-2',
      rawName: 'write_sheets_section',
      output: JSON.stringify({ slug: 'latest-news-about-ai', workspace_id: 'ws-1' }),
    });
    const card = sheetsWorkbookCardFromToolCalls([
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
      sheetsWorkbookCardFromToolCalls([toolCall({ output: CREATED_OUTPUT }), second])?.slug,
    ).toBe('second-workbook');
  });
});

describe('sheetsWorkbookTitleFromToolOutput', () => {
  it('reads the title a sheets tool result carries', () => {
    expect(sheetsWorkbookTitleFromToolOutput(CREATED_OUTPUT)).toBe('Latest News About AI');
    expect(
      sheetsWorkbookTitleFromToolOutput(
        JSON.stringify({ slug: 'materiaux-de-construction', title: 'Matériaux de construction' }),
      ),
    ).toBe('Matériaux de construction');
  });

  it('returns nothing for output with no title', () => {
    expect(sheetsWorkbookTitleFromToolOutput(undefined)).toBe('');
    expect(sheetsWorkbookTitleFromToolOutput('wrote the workbook')).toBe('');
    expect(sheetsWorkbookTitleFromToolOutput(JSON.stringify({ slug: 'x' }))).toBe('');
    expect(
      sheetsWorkbookTitleFromToolOutput(JSON.stringify({ title: 'X', error: 'nope' })),
    ).toBe('');
  });
});

describe('sheetsWorkbookHref', () => {
  it('links into the Sheets surface for the workbook workspace', () => {
    expect(
      sheetsWorkbookHref({ slug: 'ai', title: 'AI', workspaceId: 'ws-1' }, 'ws-current'),
    ).toBe('/workspace/ws-1/sheets/ai');
  });

  it('falls back to the current workspace when the tool omitted one', () => {
    expect(
      sheetsWorkbookHref({ slug: 'ai', title: 'AI', workspaceId: '' }, 'ws-current'),
    ).toBe('/workspace/ws-current/sheets/ai');
  });

  it('encodes an unusual slug', () => {
    expect(
      sheetsWorkbookHref({ slug: 'a b', title: 'AI', workspaceId: 'ws-1' }, 'ws-1'),
    ).toBe('/workspace/ws-1/sheets/a%20b');
  });
});
