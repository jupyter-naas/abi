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

function titleFromSlug(slug: string): string {
  return slug
    .split('-')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function displayTitleFromResult(parsed: Record<string, unknown>): string {
  if (typeof parsed.title === 'string' && parsed.title.trim()) {
    return parsed.title.trim();
  }
  if (typeof parsed.name === 'string' && parsed.name.trim()) {
    return parsed.name.trim();
  }
  return '';
}

/**
 * True when tool JSON looks like a deck create/write/publish result.
 *
 * Contract (tool-name agnostic):
 * - non-empty ``slug``
 * - optional display name via ``title`` or ``name`` (slug title-cased if absent)
 * - if ``nexus_shipped`` is present (publish-style), require ``ok === true`` and
 *   ``nexus_shipped === true`` so failed/partial publishes never render a card
 */
export function isSlidesDeckResult(parsed: Record<string, unknown>): boolean {
  if (!parsed || typeof parsed !== 'object' || parsed.error) return false;
  const slug = typeof parsed.slug === 'string' ? parsed.slug.trim() : '';
  if (!slug) return false;
  if ('nexus_shipped' in parsed) {
    return parsed.ok === true && parsed.nexus_shipped === true;
  }
  return true;
}

/**
 * Derive the deck to surface for an assistant message, or null when the turn
 * did not touch one. A create wins over a later write on the same deck,
 * because only create carries the title the user asked for.
 *
 * Detection is by result shape (see ``isSlidesDeckResult``), not tool name.
 */
export function slidesDeckCardFromToolCalls(
  toolCalls: ToolCall[] | undefined,
): SlidesDeckCard | null {
  let slug = '';
  let title = '';
  let workspaceId = '';
  for (const call of toolCalls ?? []) {
    if (call.status !== 'done' || !call.output) continue;

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(call.output) as Record<string, unknown>;
    } catch {
      continue; // Tool output can be plain text.
    }
    if (!isSlidesDeckResult(parsed)) continue;

    const nextSlug = typeof parsed.slug === 'string' ? parsed.slug.trim() : '';
    if (!nextSlug) continue;

    // Moving to a different deck drops the previous title; a later write on
    // the same deck keeps the title the create carried.
    if (nextSlug !== slug) {
      slug = nextSlug;
      title = '';
    }
    const nextTitle = displayTitleFromResult(parsed);
    if (nextTitle) {
      title = nextTitle;
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
  return displayTitleFromResult(parsed);
}

export function slidesDeckHref(card: SlidesDeckCard, currentWorkspaceId: string): string {
  const ws = card.workspaceId || currentWorkspaceId;
  return `/workspace/${encodeURIComponent(ws)}/slides/${encodeURIComponent(card.slug)}`;
}
