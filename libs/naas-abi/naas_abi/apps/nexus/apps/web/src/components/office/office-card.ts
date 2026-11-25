/**
 * Cards shown in chat for a document, workbook or deck Abi built.
 *
 * When Abi builds one from the ordinary chat surface there is no Documents, Sheets
 * or Slides page to show it on, so the assistant message renders a card that opens
 * it. The chat stream already records every tool call with its JSON output, so the
 * card is derived from that rather than adding a parallel channel.
 */

import type { ToolCall } from '@/stores/workspace';
import type { OfficeKindId } from './office-kinds';

export type OfficeCard = {
  slug: string;
  title: string;
  workspaceId: string;
};

type Result = Record<string, unknown>;

/** How one kind recognises its results in a turn's tool calls. */
export type OfficeCardRules = {
  /** Only these tools count. Absent: any tool whose result has the right shape. */
  matchesTool?: (rawName: string) => boolean;
  /** A result that names an item. */
  accepts: (parsed: Result) => boolean;
  /** The display name a result carries, or "". */
  title: (parsed: Result) => string;
};

function trimmed(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function isResult(parsed: Result): boolean {
  return Boolean(parsed) && typeof parsed === 'object' && !parsed.error;
}

/** Documents and Sheets: a write tool's result, titled by `title`. */
function byToolName(names: string[], normalize: (raw: string) => string): OfficeCardRules {
  return {
    matchesTool: (rawName) => {
      const raw = normalize(rawName);
      return names.some((name) => raw.includes(name));
    },
    accepts: isResult,
    title: (parsed) => trimmed(parsed.title),
  };
}

export const OFFICE_CARD_RULES: Record<OfficeKindId, OfficeCardRules> = {
  // Live stream keeps snake_case; persisted steps store the human label
  // ("Fill Document Slots"). Collapse both so the chat card still matches.
  documents: byToolName(
    [
      'create_documents_project',
      'write_document',
      'fill_document_slots',
      'replace_in_document',
      'rename_document',
      'update_title',
    ],
    (raw) => raw.toLowerCase().replace(/[\s-]+/g, '_'),
  ),
  sheets: byToolName(['create_sheets_project', 'write_sheets', 'replace_in_sheets'], (raw) => raw.toLowerCase()),
  /**
   * Slides detect by result shape, not tool name:
   * - non-empty ``slug``
   * - optional display name via ``title`` or ``name`` (slug title-cased if absent)
   * - if ``nexus_shipped`` is present (publish-style), require ``ok === true`` and
   *   ``nexus_shipped === true`` so failed/partial publishes never render a card
   */
  slides: {
    accepts: (parsed) => {
      if (!isResult(parsed) || !trimmed(parsed.slug)) return false;
      if ('nexus_shipped' in parsed) return parsed.ok === true && parsed.nexus_shipped === true;
      return true;
    },
    title: (parsed) => trimmed(parsed.title) || trimmed(parsed.name),
  },
};

function titleFromSlug(slug: string): string {
  return slug
    .split('-')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Derive the item to surface for an assistant message, or null when the turn did
 * not touch one. A create wins over a later write on the same item, because only
 * create carries the title the user asked for.
 */
export function officeCardFromToolCalls(
  kind: OfficeKindId,
  toolCalls: ToolCall[] | undefined,
): OfficeCard | null {
  const rules = OFFICE_CARD_RULES[kind];
  let slug = '';
  let title = '';
  let workspaceId = '';
  for (const call of toolCalls ?? []) {
    if (call.status !== 'done' || !call.output) continue;
    if (rules.matchesTool && !rules.matchesTool(call.rawName || call.toolName || '')) continue;

    let parsed: Result;
    try {
      parsed = JSON.parse(call.output) as Result;
    } catch {
      continue; // Tool output can be plain text.
    }
    if (!rules.accepts(parsed)) continue;

    const nextSlug = trimmed(parsed.slug);
    if (!nextSlug) continue;

    // Moving to a different item drops the previous title; a later write on the
    // same item keeps the title the create carried.
    if (nextSlug !== slug) {
      slug = nextSlug;
      title = '';
    }
    const nextTitle = rules.title(parsed);
    if (nextTitle) title = nextTitle;
    if (trimmed(parsed.workspace_id)) workspaceId = trimmed(parsed.workspace_id);
  }
  if (!slug) return null;
  return { slug, title: title || titleFromSlug(slug), workspaceId };
}

/**
 * Title a tool result carries, or "" when it has none.
 *
 * Writes report the item's display name, which is how the pane header and the
 * sidebar tree learn that Abi just named an item after the brief.
 */
export function officeTitleFromToolOutput(kind: OfficeKindId, output: string | undefined): string {
  if (!output || !output.trim()) return '';
  let parsed: Result;
  try {
    parsed = JSON.parse(output) as Result;
  } catch {
    return ''; // Tool output can be plain text.
  }
  if (!isResult(parsed)) return '';
  return OFFICE_CARD_RULES[kind].title(parsed);
}

export function officeCardHref(kind: OfficeKindId, card: OfficeCard, currentWorkspaceId: string): string {
  const ws = card.workspaceId || currentWorkspaceId;
  return `/workspace/${encodeURIComponent(ws)}/${kind}/${encodeURIComponent(card.slug)}`;
}
