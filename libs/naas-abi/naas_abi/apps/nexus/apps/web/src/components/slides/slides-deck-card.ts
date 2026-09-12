/**
 * Deck cards shown in chat.
 *
 * When Abi builds a deck from the ordinary chat surface there is no Slides
 * page to show it on, so the assistant message renders a card that opens the
 * deck. The chat stream already records every tool call with its JSON output,
 * so the card is derived from that rather than adding a parallel channel.
 */

import type { ToolCall } from '@/stores/workspace';

export type SlidesDeckCard = {
  slug: string;
  title: string;
  workspaceId: string;
};

const CREATE_TOOL = 'create_slides_project';

function isSlidesDeckTool(rawName: string | null | undefined): boolean {
  const raw = (rawName || '').toLowerCase();
  return (
    raw.includes(CREATE_TOOL) ||
    raw.includes('write_slides') ||
    raw.includes('replace_in_slides') ||
    raw.includes('rename_deck') ||
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
 * Derive the deck to surface for an assistant message, or null when the turn
 * did not touch one. A create wins over a later write on the same deck,
 * because only create carries the title the user asked for.
 */
export function slidesDeckCardFromToolCalls(
  toolCalls: ToolCall[] | undefined,
): SlidesDeckCard | null {
  let slug = '';
  let title = '';
  let workspaceId = '';
  for (const call of toolCalls ?? []) {
    if (call.status !== 'done' || !call.output) continue;
    if (!isSlidesDeckTool(call.rawName || call.toolName)) continue;

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(call.output) as Record<string, unknown>;
    } catch {
      continue; // Tool output can be plain text.
    }
    if (!parsed || typeof parsed !== 'object' || parsed.error) continue;

    const nextSlug = typeof parsed.slug === 'string' ? parsed.slug.trim() : '';
    if (!nextSlug) continue;

    // Moving to a different deck drops the previous title; a later write on
    // the same deck keeps the title the create carried.
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
 * Title a slides tool result carries, or "" when it has none.
 *
 * Slides writes report the deck's display name, which is how the pane header
 * and the sidebar tree learn that Abi just named a deck after the brief.
 */
export function slidesDeckTitleFromToolOutput(output: string | undefined): string {
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

export function slidesDeckHref(card: SlidesDeckCard, currentWorkspaceId: string): string {
  const ws = card.workspaceId || currentWorkspaceId;
  return `/workspace/${encodeURIComponent(ws)}/slides/${encodeURIComponent(card.slug)}`;
}
