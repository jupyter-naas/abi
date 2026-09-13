/**
 * Document cards shown in chat.
 *
 * When Abi builds a document from the ordinary chat surface there is no Documents
 * page to show it on, so the assistant message renders a card that opens the
 * document. The chat stream already records every tool call with its JSON output,
 * so the card is derived from that rather than adding a parallel channel.
 */

import type { ToolCall } from '@/stores/workspace';

export type DocumentsCard = {
  slug: string;
  title: string;
  workspaceId: string;
};

const CREATE_TOOL = 'create_documents_project';

function normalizeToolName(rawName: string | null | undefined): string {
  // Live stream keeps snake_case; persisted steps store the human label
  // ("Fill Document Slots"). Collapse both so the chat card still matches.
  return (rawName || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function isDocumentsWriteTool(rawName: string | null | undefined): boolean {
  const raw = normalizeToolName(rawName);
  return (
    raw.includes(CREATE_TOOL) ||
    raw.includes('write_document') ||
    raw.includes('fill_document_slots') ||
    raw.includes('replace_in_document') ||
    raw.includes('rename_document') ||
    raw.includes('update_title')
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
 * Derive the document to surface for an assistant message, or null when the turn
 * did not touch one. A create wins over a later write on the same document,
 * because only create carries the title the user asked for.
 */
export function sectionsDocumentCardFromToolCalls(
  toolCalls: ToolCall[] | undefined,
): DocumentsCard | null {
  let slug = '';
  let title = '';
  let workspaceId = '';
  for (const call of toolCalls ?? []) {
    if (call.status !== 'done' || !call.output) continue;
    if (!isDocumentsWriteTool(call.rawName || call.toolName)) continue;

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(call.output) as Record<string, unknown>;
    } catch {
      continue; // Tool output can be plain text.
    }
    if (!parsed || typeof parsed !== 'object' || parsed.error) continue;

    const nextSlug = typeof parsed.slug === 'string' ? parsed.slug.trim() : '';
    if (!nextSlug) continue;

    // Moving to a different document drops the previous title; a later write on
    // the same document keeps the title the create carried.
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
 * Title a sections tool result carries, or "" when it has none.
 *
 * Documents writes report the document's display name, which is how the pane header
 * and the sidebar tree learn that Abi just named a document after the brief.
 */
export function sectionsDocumentTitleFromToolOutput(output: string | undefined): string {
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

export function sectionsDocumentHref(card: DocumentsCard, currentWorkspaceId: string): string {
  const ws = card.workspaceId || currentWorkspaceId;
  return `/workspace/${encodeURIComponent(ws)}/documents/${encodeURIComponent(card.slug)}`;
}
