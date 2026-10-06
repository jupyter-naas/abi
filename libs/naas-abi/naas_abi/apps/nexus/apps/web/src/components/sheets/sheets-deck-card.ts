/**
 * Workbook cards shown in chat.
 *
 * When Abi builds a workbook from the ordinary chat surface there is no Sheets
 * page to show it on, so the assistant message renders a card that opens the
 * workbook. The chat stream already records every tool call with its JSON output,
 * so the card is derived from that rather than adding a parallel channel.
 */

import type { ToolCall } from '@/stores/workspace';

export type SheetsWorkbookCard = {
  slug: string;
  title: string;
  workspaceId: string;
};

const CREATE_TOOL = 'create_sheets_project';

function isSheetsWorkbookTool(rawName: string | null | undefined): boolean {
  const raw = (rawName || '').toLowerCase();
  return (
    raw.includes(CREATE_TOOL) ||
    raw.includes('write_sheets') ||
    raw.includes('replace_in_sheets')
  );
}

function titleFromSlug(slug: string): string {
  return slug
    .split('-')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Derive the workbook to surface for an assistant message, or null when the turn
 * did not touch one. A create wins over a later write on the same workbook,
 * because only create carries the title the user asked for.
 */
export function sheetsWorkbookCardFromToolCalls(
  toolCalls: ToolCall[] | undefined,
): SheetsWorkbookCard | null {
  let slug = '';
  let title = '';
  let workspaceId = '';
  for (const call of toolCalls ?? []) {
    if (call.status !== 'done' || !call.output) continue;
    if (!isSheetsWorkbookTool(call.rawName || call.toolName)) continue;

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(call.output) as Record<string, unknown>;
    } catch {
      continue; // Tool output can be plain text.
    }
    if (!parsed || typeof parsed !== 'object' || parsed.error) continue;

    const nextSlug = typeof parsed.slug === 'string' ? parsed.slug.trim() : '';
    if (!nextSlug) continue;

    // Moving to a different workbook drops the previous title; a later write on
    // the same workbook keeps the title the create carried.
    if (nextSlug !== slug) {
      slug = nextSlug;
      title = '';
    }
    if (typeof parsed.title === 'string' && parsed.title.trim()) {
      title = parsed.title.trim();
    }
    if (typeof parsed.workspace_id === 'string' && parsed.workspace_id.trim()) {
      workspaceId = parsed.workspace_id.trim();
    }
  }
  if (!slug) return null;
  return { slug, title: title || titleFromSlug(slug), workspaceId };
}

/**
 * Title a sheets tool result carries, or "" when it has none.
 *
 * Sheets writes report the workbook's display name, which is how the pane header
 * and the sidebar tree learn that Abi just named a workbook after the brief.
 */
export function sheetsWorkbookTitleFromToolOutput(output: string | undefined): string {
  if (!output || !output.trim()) return '';
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(output) as Record<string, unknown>;
  } catch {
    return ''; // Tool output can be plain text.
  }
  if (!parsed || typeof parsed !== 'object' || parsed.error) return '';
  return typeof parsed.title === 'string' ? parsed.title.trim() : '';
}

export function sheetsWorkbookHref(card: SheetsWorkbookCard, currentWorkspaceId: string): string {
  const ws = card.workspaceId || currentWorkspaceId;
  return `/workspace/${encodeURIComponent(ws)}/sheets/${encodeURIComponent(card.slug)}`;
}
